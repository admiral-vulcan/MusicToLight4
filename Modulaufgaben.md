Modulaufgaben (Kurzbeschreibung)
app.py: Einstiegspunkt, liest Konfiguration, startet Orchestrator und hält die Mainloop ähnlich zur bisherigen main.py, nur mit klar getrennten Abhängigkeiten.

config.py: Sammelstelle für Gerätekonfigurationen, Netzwerkadressen, Audiopuffergrößen usw., die bislang in mehreren Modulen verstreut sind (z. B. Buffer und Sample-Raten aus aud_proc.py, UDP-Adressen aus com_udp.py).

bootstrap.py: Setzt Umgebungsvariablen (SDL/X11) und initialisiert optionale Komponenten wie HDMI, analog zu den Setup-Zeilen aus main.py.

core/audio_pipeline.py: Kapselt Audioeinlesen, Filter und Merkmalsextraktion aus aud_proc.py in eine zustandsbehaftete Pipeline-Klasse.

core/cue_engine.py: Implementiert die Logik, welche Audio- und GUI-Eingaben in Licht-/Video-Cues übersetzt (Panikmodus, Strobe, Chill usw., vormals direkt in main.py).

core/state_model.py: Zentraler Zustand (Laufzeit-Zähler, Modi, zuletzt gesendete Farben), der bisher als globale Variablen in main.py verteilt war.

core/timeline.py: Koordiniert zeitliche Effekte (z. B. Glitch-Timer, Drop-Erkennung) und bietet Ticker-basierte Hooks für Services.

devices/eurolite_t36.py: Übernimmt die bestehende DMX-/Eurolite-Logik unverändert in eine gerätespezifische Klasse, damit die DMX-Pakete weiter wie gewohnt gesendet werden.

devices/laser_scanner.py: Beinhaltet Scanner-Ansteuerung aus scanner.py/laser_show.py, verpackt als Strategie-Objekte für den Orchestrator.

devices/led_strip.py: Enthält den UDP-NeoPixel-Adapter und LED-Effekte, damit die bisherigen UDP-Pakete identisch rausgehen.

devices/spectrum_analyzer.py: Verpackt das Zusammenstellen und Senden der Analyzer-Pakete (send_spectrum_analyzer_data) in eine Klasse mit Device-Interface.

outputs/hdmi_display.py: Stellt Zeichenfunktionen, Text-/Matrix-Rendering und Glitch-Effekte bereit, getrennt von der Video-Abspiellogik.

outputs/video_player.py: Verwaltet das Video-Playlist-Handling und Autoplay-Verhalten, sodass HDMI-Rendering davon entkoppelt bleibt.

transport/gui_bridge.py: Fragt GUI-Kommandos ab, entpackt die redis-/Netzwerkdaten und gibt sie strukturiert an den Orchestrator weiter (ersetzt get_gui_commands()-Nutzung direkt in main.py).

transport/udp_client.py: Allgemeiner Thread-sicherer UDP-Versand als Wrapper um die heutige send_udp_message-Implementierung, damit alle Geräte dieselbe Schnittstelle nutzen.

services/orchestrator.py: Herzstück, das Audioevents, GUI-Befehle und Gerätestati zusammenführt, um Ausgaben auszulösen – ersetzt die verschachtelte while-Schleife aus main.py.

services/effect_presets.py: Bündelt wiederverwendbare LED-/DMX-/HDMI-Presets (z. B. Panic-Mode, Chill-Mode), die bisher an mehreren Stellen inline codiert sind.

services/safety.py: Behandelt Safe-States (z. B. alle LEDs auf Schwarz, Panic-Mode-Abbruch-Schleifen).

utils/logging.py, utils/math_helpers.py, utils/timing.py: Helfer, die aus dem bisherigen helpers.py und verstreuten Funktionen herausgelöst werden, damit alle Module dieselben Utility-Funktionen benutzen.

