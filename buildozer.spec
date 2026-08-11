[app]
title = Super Jump Racer
package.name = superjumpracer
package.domain = org.cezar.superjumpracer

source.dir = .
source.include_exts = py,png,mp3,wav,txt

version = 2.0

# Os assets (sprites e musica) ja vem prontos na pasta assets/, entao
# o jogo nao precisa gerar nada em tempo real -> nao precisamos
# incluir numpy nem pillow como dependencia (build mais rapido e
# confiavel).
requirements = python3,pygame-ce

orientation = landscape
fullscreen = 1

icon.filename = %(source.dir)s/assets/robot_yellow.png

# evita que o build trave esperando confirmacao interativa da
# licenca do Android SDK (comum em CI/GitHub Actions)
android.accept_sdk_license = True
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
