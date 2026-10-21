import main.DataReadingManager;
import main.DataWritingManager;
import model.MonsterStatDataObject;
import model.strings.KeyedString;
import reading.BytesHelper;
import reading.DataFileReader;
import reading.FileAccessorWithMods;

import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

public class MonsterTextSplice {
    public static void main(String[] args) throws Exception {
        FileAccessorWithMods.GAME_FILES_ROOT = "./";
        DataReadingManager.initializeInternals();
        DataReadingManager.readAndPrepareDataModel();
        try (PrintStream progress = KernelSplice.progress(args.length / 4)) {
            for (int i = 0; i + 3 < args.length; i += 4) {
                splice(args[i], args[i + 1], Integer.parseInt(args[i + 2]), args[i + 3]);
                progress.println(args[i]);
            }
        }
    }

    private static void splice(String discPath, String spanishPath, int monster, String outputPath) throws Exception {
        byte[] disc = Files.readAllBytes(Path.of(discPath));
        MonsterStatDataObject object = parsed(disc, KernelSplice.DISC_LOCALIZATION);
        Set<Integer> discHeaders = object.streamKeyedStrings(KernelSplice.DISC_LOCALIZATION).map(KeyedString::toHeaderBytes).collect(Collectors.toSet());
        DataFileReader<MonsterStatDataObject> reader = new DataFileReader<>(MonsterStatDataObject::new, MonsterStatDataObject[]::new);
        MonsterStatDataObject[] spanish = reader.toArray(spanishPath, KernelSplice.SPANISH_LOCALIZATION, false);
        int record = monster - KernelSplice.read2(Files.readAllBytes(Path.of(spanishPath)), KernelSplice.HEADER_MIN_INDEX);
        if (record < 0 || record >= spanish.length) {
            throw new IllegalArgumentException("monster " + monster + " is not in " + spanishPath);
        }
        object.setLocalizations(spanish[record]);
        byte[] output = KernelSplice.signed(DataWritingManager.dataObjectWithStringsToBytes(object, KernelSplice.SPANISH_LOCALIZATION));
        KernelSplice.requireDataUnchanged(disc, output, 0, MonsterStatDataObject.LENGTH, discHeaders, "monster " + monster);
        Files.write(Path.of(outputPath), output);
        MonsterStatDataObject written = parsed(output, KernelSplice.SPANISH_LOCALIZATION);
        List<List<String>> expected = KernelSplice.strings(new MonsterStatDataObject[]{spanish[record]}, KernelSplice.SPANISH_LOCALIZATION);
        if (!KernelSplice.strings(new MonsterStatDataObject[]{written}, KernelSplice.SPANISH_LOCALIZATION).equals(expected)) {
            throw new IllegalStateException("monster " + monster + " strings differ after rebuild");
        }
    }

    private static MonsterStatDataObject parsed(byte[] bytes, String localization) {
        int[] values = BytesHelper.byteToIntArray(bytes);
        return new MonsterStatDataObject(values, Arrays.copyOfRange(values, MonsterStatDataObject.LENGTH, values.length), localization);
    }
}
