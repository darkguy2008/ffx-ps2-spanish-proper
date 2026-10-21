import main.DataReadingManager;
import main.DataWritingManager;
import model.*;
import model.spheregrid.*;
import model.strings.KeyedString;
import reading.DataFileReader;
import reading.DataObjectCreator;
import reading.FileAccessorWithMods;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.IntFunction;
import java.util.stream.Collectors;

public class KernelSplice {
    static final int HEADER_MIN_INDEX = 0x08;
    private static final int HEADER_RECORD_LENGTH = 0x0C;
    private static final int HEADER_SIZE = 0x14;
    private static final int STRING_HEADER_SIZE = 4;
    static final String DISC_LOCALIZATION = "us";
    static final String SPANISH_LOCALIZATION = "sp";
    private static final String PROGRESS_FD = "PROGRESS_FD";

    private record StringEdit(String file, int record, String field, String replaces, String text) {
        StringEdit(String[] cells) {
            this(cells[0], Integer.parseInt(cells[1]), cells[2], cells[3], cells[4]);
        }
    }

    private record Kind<T extends Localized<? super T> & Writable>(DataObjectCreator<T> creator, IntFunction<T[]> arrays) {}

    private static final Map<String, Kind<?>> KINDS = Map.ofEntries(
            Map.entry("command.bin", new Kind<>((b, s, l) -> new CommandDataObject(b, s, l, 3), CommandDataObject[]::new)),
            Map.entry("monmagic1.bin", new Kind<>((b, s, l) -> new CommandDataObject(b, s, l, 4), CommandDataObject[]::new)),
            Map.entry("monmagic2.bin", new Kind<>((b, s, l) -> new CommandDataObject(b, s, l, 6), CommandDataObject[]::new)),
            Map.entry("item.bin", new Kind<>((b, s, l) -> new CommandDataObject(b, s, l, 2), CommandDataObject[]::new)),
            Map.entry("important.bin", new Kind<>(KeyItemDataObject::new, KeyItemDataObject[]::new)),
            Map.entry("a_ability.bin", new Kind<>(AutoAbilityDataObject::new, AutoAbilityDataObject[]::new)),
            Map.entry("w_name.bin", new Kind<>(WeaponNameDataObject::new, WeaponNameDataObject[]::new)),
            Map.entry("sphere.bin", new Kind<>(SphereGridSphereTypeDataObject::new, SphereGridSphereTypeDataObject[]::new)),
            Map.entry("panel.bin", new Kind<>(SphereGridNodeTypeDataObject::new, SphereGridNodeTypeDataObject[]::new)),
            Map.entry("ply_save.bin", new Kind<>(PlayerCharStatDataObject::new, PlayerCharStatDataObject[]::new)),
            Map.entry("ply_rom.bin", new Kind<>(PlayerRomDataObject::new, PlayerRomDataObject[]::new)),
            Map.entry("arms_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)),
            Map.entry("config_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)),
            Map.entry("item_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)),
            Map.entry("menu_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)),
            Map.entry("mmain_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)),
            Map.entry("status_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)),
            Map.entry("summon_txt.bin", new Kind<>(NameDescriptionTextObject::new, NameDescriptionTextObject[]::new)));

    public static void main(String[] args) throws Exception {
        FileAccessorWithMods.GAME_FILES_ROOT = "./";
        DataReadingManager.initializeInternals();
        DataReadingManager.readAndPrepareDataModel();
        File editsFile = new File(args[0]);
        if (!editsFile.exists()) {
            throw new IllegalArgumentException("missing string edits " + editsFile);
        }
        List<String[]> rows = FileAccessorWithMods.csvToList(editsFile);
        List<StringEdit> edits = rows.subList(1, rows.size()).stream().map(StringEdit::new).toList();
        Set<String> spliced = new HashSet<>();
        try (PrintStream progress = progress((args.length - 1) / 3)) {
            for (int i = 1; i + 2 < args.length; i += 3) {
                String name = Path.of(args[i + 1]).getFileName().toString();
                Kind<?> kind = KINDS.get(name);
                if (kind == null) {
                    throw new IllegalArgumentException("unsupported kernel file " + name);
                }
                splice(kind, args[i], args[i + 1], args[i + 2], edits.stream().filter(edit -> edit.file().equals(name)).toList());
                spliced.add(name);
                progress.println(args[i]);
            }
        }
        List<String> unused = edits.stream().map(StringEdit::file).filter(file -> !spliced.contains(file)).toList();
        if (!unused.isEmpty()) {
            throw new IllegalArgumentException("string edits for files not spliced: " + unused);
        }
    }

    private static <T extends Localized<? super T> & Writable> void splice(Kind<T> kind, String discPath, String spanishPath, String outputPath, List<StringEdit> edits) throws Exception {
        DataFileReader<T> reader = new DataFileReader<>(kind.creator(), kind.arrays());
        byte[] disc = Files.readAllBytes(Path.of(discPath));
        T[] objects = reader.toArray(discPath, DISC_LOCALIZATION, false);
        List<Set<Integer>> discHeaders = new ArrayList<>();
        for (T object : objects) {
            discHeaders.add(object.streamKeyedStrings(DISC_LOCALIZATION).map(KeyedString::toHeaderBytes).collect(Collectors.toSet()));
        }
        String localization = SPANISH_LOCALIZATION;
        T[] wanted = reader.toArray(spanishPath, localization, false);
        for (StringEdit edit : edits) {
            KeyedString target = wanted[edit.record()].getKeyedString(edit.field()).getLocalizedContent(localization);
            if (!target.getString().equals(edit.replaces())) {
                throw new IllegalStateException(edit + " found \"" + target.getString() + "\"");
            }
            target.setString(edit.text());
        }
        if (wanted.length != objects.length) {
            throw new IllegalStateException("record count " + objects.length + " vs " + wanted.length);
        }
        for (int i = 0; i < objects.length; i++) {
            objects[i].setLocalizations(wanted[i]);
        }
        List<List<String>> wantedStrings = strings(wanted, localization);
        int from = read2(disc, HEADER_MIN_INDEX);
        int length = read2(disc, HEADER_RECORD_LENGTH);
        byte[] output = signed(DataWritingManager.dataObjectsToBytes(objects, length, from, from + objects.length, localization, false));
        for (int record = 0; record < objects.length; record++) {
            requireDataUnchanged(disc, output, HEADER_SIZE + record * length, length, discHeaders.get(record), "record " + record);
        }
        Files.write(Path.of(outputPath), output);
        List<List<String>> written = strings(reader.toArray(outputPath, localization, false), localization);
        if (!written.equals(wantedStrings)) {
            throw new IllegalStateException("strings differ after rebuild");
        }
    }

    static PrintStream progress(int total) throws IOException {
        PrintStream progress = new PrintStream(new FileOutputStream("/dev/fd/" + System.getenv(PROGRESS_FD)), true);
        progress.println(total);
        return progress;
    }

    static byte[] signed(int[] values) {
        byte[] bytes = new byte[values.length];
        for (int i = 0; i < values.length; i++) {
            bytes[i] = (byte) values[i];
        }
        return bytes;
    }

    static void requireDataUnchanged(byte[] disc, byte[] output, int start, int length, Set<Integer> headers, String what) {
        for (int position = 0; position < length; position++) {
            if (output[start + position] != disc[start + position] && !insideStringHeader(disc, start, position, length, headers)) {
                throw new IllegalStateException(what + " data byte " + position + " changed");
            }
        }
    }

    private static boolean insideStringHeader(byte[] disc, int start, int position, int length, Set<Integer> headers) {
        for (int field = position - position % 2 - 2; field <= position; field += 2) {
            if (field >= 0 && field + STRING_HEADER_SIZE <= length && headers.contains(read4(disc, start + field))) {
                return true;
            }
        }
        return false;
    }

    static <T extends Writable> List<List<String>> strings(T[] objects, String localization) {
        return Arrays.stream(objects)
                .map(object -> object.streamKeyedStrings(localization).map(text -> text == null ? null : text.getString()).toList())
                .toList();
    }

    static int read2(byte[] bytes, int offset) {
        return (bytes[offset] & 0xff) | (bytes[offset + 1] & 0xff) << 8;
    }

    private static int read4(byte[] bytes, int offset) {
        return read2(bytes, offset) | read2(bytes, offset + 2) << 16;
    }
}
