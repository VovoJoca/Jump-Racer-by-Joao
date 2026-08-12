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
requirements = python3==3.11.9,hostpython3==3.11.9,pygame
# Fixamos o Python em 3.11.9 (em vez de deixar solto em "python3", que
# o python-for-android estava resolvendo para a versão 3.14, bem
# recente demais — causava erros de compilação em várias bibliotecas).
# O 3.11 é uma versão bem mais madura e testada por todo o ecossistema
# Kivy/Buildozer. Com o Python certo, voltamos a usar o "pygame"
# clássico (em vez do pygame-ce) — a receita oficial dele no
# python-for-android é testada há anos e não tem os problemas de
# compilação que a receita (mais nova, ainda instável) do pygame-ce
# estava causando.

orientation = landscape
fullscreen = 1

icon.filename = %(source.dir)s/assets/robot_yellow.png

# evita que o build trave esperando confirmacao interativa da
# licenca do Android SDK (comum em CI/GitHub Actions)
android.accept_sdk_license = True
android.api = 35
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
