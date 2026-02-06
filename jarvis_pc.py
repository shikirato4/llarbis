#!/usr/bin/env python3
"""Asistente de voz tipo Jarvis para control local de PC."""

from __future__ import annotations

import argparse
import platform
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from typing import Optional

import pyautogui
import pyttsx3
import speech_recognition as sr


APP_ALIASES = {
    "navegador": {
        "Windows": "start msedge",
        "Darwin": "open -a 'Safari'",
        "Linux": "xdg-open https://www.google.com",
    },
    "bloc de notas": {
        "Windows": "start notepad",
        "Darwin": "open -a TextEdit",
        "Linux": "gedit",
    },
    "terminal": {
        "Windows": "start cmd",
        "Darwin": "open -a Terminal",
        "Linux": "x-terminal-emulator",
    },
}

SITE_ALIASES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
}


@dataclass
class Intent:
    action: str
    value: Optional[str] = None


class JarvisPC:
    def __init__(self, wake_word: str, text_mode: bool, allow_unsafe: bool):
        self.wake_word = wake_word.lower().strip()
        self.text_mode = text_mode
        self.allow_unsafe = allow_unsafe
        self.recognizer = sr.Recognizer()
        self.tts = pyttsx3.init()
        self.os_name = platform.system()

        self.tts.setProperty("rate", 175)

    def speak(self, message: str) -> None:
        print(f"Jarvis: {message}")
        self.tts.say(message)
        self.tts.runAndWait()

    def listen(self) -> str:
        if self.text_mode:
            return input("Tú> ").strip().lower()

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("Escuchando...")
            audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=8)

        try:
            text = self.recognizer.recognize_google(audio, language="es-ES")
            print(f"Tú (voz): {text}")
            return text.strip().lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            self.speak("No puedo contactar el servicio de reconocimiento de voz.")
            return ""

    def wait_for_command(self) -> str:
        command = self.listen()
        if not command:
            return ""
        if self.text_mode:
            return command

        if self.wake_word and not command.startswith(self.wake_word):
            return ""

        if self.wake_word:
            command = command[len(self.wake_word) :].strip(" ,")
        return command

    def parse_intent(self, command: str) -> Intent:
        if command in {"salir", "adiós", "apagar"}:
            return Intent("exit")

        if command in {"ayuda", "qué puedes hacer", "comandos"}:
            return Intent("help")

        if match := re.match(r"(?:abre|abrir) (.+)", command):
            return Intent("open", match.group(1).strip())

        if match := re.match(r"(?:escribe|escribir) (.+)", command):
            return Intent("type", match.group(1).strip())

        if match := re.match(r"mueve mouse (arriba|abajo|izquierda|derecha)", command):
            return Intent("move_mouse", match.group(1).strip())

        if command in {"clic", "click", "haz clic"}:
            return Intent("click")

        if match := re.match(r"(?:ejecuta|ejecutar) comando (.+)", command):
            return Intent("run_shell", match.group(1).strip())

        return Intent("unknown", command)

    def confirm(self, question: str) -> bool:
        if self.allow_unsafe:
            return True

        self.speak(f"Confirmación requerida: {question}. Responde sí o no.")
        answer = self.listen()
        return answer in {"si", "sí", "confirmo", "ok", "vale"}

    def open_target(self, target: str) -> None:
        if target in SITE_ALIASES:
            webbrowser.open(SITE_ALIASES[target])
            self.speak(f"Abriendo {target}.")
            return

        app = APP_ALIASES.get(target)
        if app:
            cmd = app.get(self.os_name)
            if cmd:
                subprocess.Popen(cmd, shell=True)
                self.speak(f"Abriendo {target}.")
                return

        if target.startswith("http://") or target.startswith("https://"):
            webbrowser.open(target)
            self.speak("Sitio web abierto.")
            return

        self.speak(f"No tengo configurado: {target}.")

    def move_mouse(self, direction: str) -> None:
        delta = 120
        dx, dy = 0, 0
        if direction == "arriba":
            dy = -delta
        elif direction == "abajo":
            dy = delta
        elif direction == "izquierda":
            dx = -delta
        elif direction == "derecha":
            dx = delta

        pyautogui.moveRel(dx, dy, duration=0.2)
        self.speak(f"Moviendo mouse {direction}.")

    def run_shell(self, cmd: str) -> None:
        if not self.confirm(f"ejecutar el comando {cmd}"):
            self.speak("Comando cancelado.")
            return

        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            output = (completed.stdout or completed.stderr or "sin salida").strip()
            output = output[:450]
            self.speak(f"Comando ejecutado con código {completed.returncode}.")
            print(f"Salida:\n{output}")
        except subprocess.TimeoutExpired:
            self.speak("El comando tardó demasiado y fue cancelado.")

    def handle_intent(self, intent: Intent) -> bool:
        if intent.action == "exit":
            self.speak("Hasta luego.")
            return False

        if intent.action == "help":
            self.speak(
                "Puedes pedirme abrir apps o webs, escribir texto, mover mouse, hacer clic y ejecutar comandos."
            )
            return True

        if intent.action == "open" and intent.value:
            self.open_target(intent.value)
            return True

        if intent.action == "type" and intent.value:
            pyautogui.write(intent.value, interval=0.03)
            self.speak("Texto escrito.")
            return True

        if intent.action == "move_mouse" and intent.value:
            self.move_mouse(intent.value)
            return True

        if intent.action == "click":
            pyautogui.click()
            self.speak("Clic realizado.")
            return True

        if intent.action == "run_shell" and intent.value:
            self.run_shell(intent.value)
            return True

        self.speak("No entendí ese comando. Di ayuda para ver opciones.")
        return True

    def run(self) -> int:
        self.speak("Jarvis PC iniciado.")

        while True:
            try:
                command = self.wait_for_command()
                if not command:
                    continue
                intent = self.parse_intent(command)
                should_continue = self.handle_intent(intent)
                if not should_continue:
                    return 0
            except KeyboardInterrupt:
                self.speak("Interrumpido por teclado. Cerrando.")
                return 0
            except Exception as exc:  # pylint: disable=broad-except
                self.speak("Ocurrió un error interno.")
                print(f"Error: {exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Asistente por voz tipo Jarvis para PC.")
    parser.add_argument("--wake-word", default="jarvis", help="Palabra de activación.")
    parser.add_argument(
        "--text-mode",
        action="store_true",
        help="Usa entrada de texto en vez de micrófono.",
    )
    parser.add_argument(
        "--allow-unsafe",
        action="store_true",
        help="Omite confirmaciones antes de comandos peligrosos.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    assistant = JarvisPC(
        wake_word=args.wake_word,
        text_mode=args.text_mode,
        allow_unsafe=args.allow_unsafe,
    )
    return assistant.run()


if __name__ == "__main__":
    raise SystemExit(main())
