# Final Fantasy X International — Español (PS2)

Bueno, primero lo primero, **me encanta** este juego! (No tanto como FFIX, pero ajá) perooooo siempre me sacaba de quicio que la versión en español fuera PAL (horribles los 50Hz, lo siento tíos! xD) y que lo único que haya salido en 60Hz hayan sido otros idiomas menos español. Tampoco me gustaron mucho los gráficos del remaster, y si quieres la experiencia original pero en español, es imposible hacerlo sin el remaster.

Entonces bueno, hice esta app que convierte **tu propia copia** de **Final Fantasy X International** (Japón, PS2) en un ISO en español, NTSC, 60hz (AL FIN!). Por qué esta versión? Es la misma del remaster, tiene los Dark Aeons y todo el contenido extra. Pensaba hacerlo con la normal de PAL, pero como el remaster fue basado en el International, pues por qué no?

Obvio todo esto asistido por mi gran amigo Claudio, pero vamos, tengo ya más de 20 años programando y *sé cómo va el rollo*. Fue hecho con cariño, tomando en cuenta los pequeños detalles. No lo he terminado, apenas llegué a Besaid, pero eso ya confirma que las FMVs, cutscenes, menús, guardado, batallas y etc. funcionan sin problema.

Por razones obvias, acá no vas a conseguir los datos del juego. Tienes que tener los tuyos propios.

## Qué hace?

Toma el texto en español del HD Remaster de Steam. Toma la fuente, las etiquetas de los menús, las pantallas de ayuda y la pantalla de título en español del disco PAL español. Soporta Japonés y Español correctamente, fue un reemplazo bien hecho para que se sintiera lo más "oficial" posible. ✕ confirma y ○ cancela, como debe ser!

## Qué necesitas

1. **Final Fantasy X International (Japan) (En,Ja)**, SLPS-25088, como ISO. Debe coincidir con el [disco 17929 de Redump](http://redump.org/disc/17929/): SHA-1 `6c97681f621716024f9a16f84c0835c06dd4bfd7`.
2. **Final Fantasy X (Spain)**, SCES-50494, como ISO. Debe coincidir con el [disco 5353 de Redump](http://redump.org/disc/5353/): SHA-1 `6f69e3a99204fbcf236829e9ceafade33e5bf6e4`.
3. **`FFX_Data.vbf`** del juego de Steam *FINAL FANTASY X/X-2 HD Remaster*. Está en la carpeta `data` de la carpeta de instalación del juego.
4. [Docker](https://docs.docker.com/get-docker/) (Docker Desktop en Windows y macOS).

## Por qué Docker?

Había pensado en un binario, pero se requieren varias cosas, entre el extractor de vbf y el app que edita los archivos, unos usan Java, el otro Mono... Iba a ser complicado. Instalar Docker son 3 pasos nada más, es universal, funciona en cualquier OS. Ya podría hacerle un interfaz todo bonito pero ni idea si realmente hay interés en esto. Si veo que están teniendo muchos problemas corriéndolo (que no debería) pues ahí ya veo qué me invento.

El app revisa ambas ISO antes de empezar. Si un dump es incorrecto o está dañado, se detiene con un mensaje.

## Cómo parchear?

Esto lo pueden hacer en Linux o en macOS (recomiendo tener instalado homebrew y Docker Desktop) y en Windows quizás con WSL2.

1. Descarga el código con sus dos herramientas (`--recursive` es importante):

   ```sh
   git clone --recursive https://github.com/darkguy2008/ffx-ps2-spanish-proper.git
   cd ffx-ps2-spanish-proper
   ```

2. Construye la imagen del app:

   ```sh
   docker build -t ffx-ps2-spanish .
   ```

3. Pon las dos ISO y `FFX_Data.vbf` en una carpeta. Luego corre el app sobre esa carpeta. Cambia `/path/to/folder` por tu carpeta, y los nombres de archivo por los tuyos:

   ```sh
   docker run --rm -it -v "/path/to/folder:/data" ffx-ps2-spanish \
     "/data/Final Fantasy X International (Japan) (En,Ja).iso" \
     "/data/Final Fantasy X (Spain).iso" \
     /data/FFX_Data.vbf \
     /data/ffx_es.iso
   ```

El app muestra cada paso y una barra de progreso:

1. Revisa la ISO International.
2. Revisa la ISO de España.
3. Extrae los archivos de PS2 del remaster desde `FFX_Data.vbf`.
4. Cataloga la ISO International.
5. Cataloga la ISO de España.
6. Construye la ISO en español.
7. Verifica la ISO en español.

La ISO en español queda en tu carpeta como `ffx_es.iso`.

## Cómo jugar

- Empieza una **Nueva partida**. En la pantalla de idioma, elige **Español**.
- ✕ confirma y ○ cancela, como debe ser!

## Créditos

- Traducción al español: Square Enix (HD Remaster y versión PAL). **No se incluye aquí.**
- [FFXDataParser](https://github.com/Karifean/FFXDataParser) de Karifean (MIT), usado para reconstruir las tablas de texto del juego.
- [vbfextract](https://github.com/topher-au/vbfextract) de topher-au, usado para leer `FFX_Data.vbf`.

---

# Final Fantasy X International — Spanish (PS2)

Well, first things first: I **love** this game! (Not as much as FFIX, but yeah.) Buuuut it always drove me nuts that the Spanish version was PAL (50Hz is awful, sorry guys! xD) and that the only 60Hz releases came in every language except Spanish. I didn't like the remaster's graphics much either, and if you want the original experience in Spanish, you can't get it without the remaster.

So I made this app. It turns **your own copy** of **Final Fantasy X International** (Japan, PS2) into a Spanish, NTSC, 60Hz ISO (FINALLY!). Why this version? It's the same one the remaster uses, with the Dark Aeons and all the extra content. I thought about doing it with the regular PAL one, but since the remaster was based on International, why not?

Of course all of this was assisted by my good friend Claudio, but hey, I've been programming for over 20 years and *I know how this goes*. It was made with care, minding the little details. I haven't finished the game yet, I only got as far as Besaid, but that already confirms that the FMVs, cutscenes, menus, saving, battles and so on all work fine.

For obvious reasons, you won't find any game data here. You need your own.

## What does it do?

It takes the Spanish text from the Steam HD Remaster. It takes the Spanish font, menu labels, help screens and title screen from the Spanish PAL disc. It supports Japanese and Spanish properly: the replacement was done carefully so it feels as "official" as possible. ✕ confirms and ○ cancels, as it should be!

## What you need

1. **Final Fantasy X International (Japan) (En,Ja)**, SLPS-25088, as an ISO. It must match [Redump disc 17929](http://redump.org/disc/17929/): SHA-1 `6c97681f621716024f9a16f84c0835c06dd4bfd7`.
2. **Final Fantasy X (Spain)**, SCES-50494, as an ISO. It must match [Redump disc 5353](http://redump.org/disc/5353/): SHA-1 `6f69e3a99204fbcf236829e9ceafade33e5bf6e4`.
3. **`FFX_Data.vbf`** from the Steam game *FINAL FANTASY X/X-2 HD Remaster*. It is in the `data` folder of the game's install folder.
4. [Docker](https://docs.docker.com/get-docker/) (Docker Desktop on Windows and macOS).

## Why Docker?

I thought about a single binary, but it needs several things: between the VBF extractor and the app that edits the files, one uses Java and the other Mono... It was going to get complicated. Installing Docker is just 3 steps, it's universal, it works on any OS. I could build a pretty UI for it, but I have no idea if anyone's really interested. If I see people having lots of trouble running it (they shouldn't), then I'll figure something out.

The app checks both ISOs before it starts. If a dump is wrong or damaged, it stops with a message.

## How to patch?

You can do this on Linux or macOS (I recommend having Homebrew and Docker Desktop installed), and on Windows maybe with WSL2.

1. Get the code, with its two tools (`--recursive` matters):

   ```sh
   git clone --recursive https://github.com/darkguy2008/ffx-ps2-spanish-proper.git
   cd ffx-ps2-spanish-proper
   ```

2. Build the app image:

   ```sh
   docker build -t ffx-ps2-spanish .
   ```

3. Put the two ISOs and `FFX_Data.vbf` in one folder. Then run the app on that folder. Replace `/path/to/folder` with your folder, and the file names with yours:

   ```sh
   docker run --rm -it -v "/path/to/folder:/data" ffx-ps2-spanish \
     "/data/Final Fantasy X International (Japan) (En,Ja).iso" \
     "/data/Final Fantasy X (Spain).iso" \
     /data/FFX_Data.vbf \
     /data/ffx_es.iso
   ```

The app shows each step and a progress bar:

1. Check the International ISO.
2. Check the Spain ISO.
3. Extract the remaster's PS2 files from `FFX_Data.vbf`.
4. Catalog the International ISO.
5. Catalog the Spain ISO.
6. Build the Spanish ISO.
7. Verify the Spanish ISO.

The Spanish ISO is written to your folder as `ffx_es.iso`.

## How to play

- Start a **New Game** (**Nueva partida**). On the language screen, pick **Español**.
- ✕ confirms and ○ cancels, as it should be!

## Credits

- Spanish translation: Square Enix (HD Remaster and PAL release). **Not included here.**
- [FFXDataParser](https://github.com/Karifean/FFXDataParser) by Karifean (MIT), used to rebuild the game's text tables.
- [vbfextract](https://github.com/topher-au/vbfextract) by topher-au, used to read `FFX_Data.vbf`.
