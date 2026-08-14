"""Instala una vez el modelo local inglés→español de Argos Translate."""

from argostranslate import package, translate


def main() -> int:
    idiomas = {idioma.code for idioma in translate.get_installed_languages()}
    if {"en", "es"}.issubset(idiomas):
        print("El traductor ingles-espanol ya esta instalado.")
        return 0

    print("Buscando el modelo oficial ingles-espanol...")
    package.update_package_index()
    candidatos = [
        modelo
        for modelo in package.get_available_packages()
        if modelo.from_code == "en" and modelo.to_code == "es"
    ]
    if not candidatos:
        print("No se encontro el modelo ingles-espanol.")
        return 1

    modelo = candidatos[0]
    print("Descargando el modelo. Esto puede tardar varios minutos...")
    package.install_from_path(modelo.download())
    print("Traductor local ingles-espanol instalado correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
