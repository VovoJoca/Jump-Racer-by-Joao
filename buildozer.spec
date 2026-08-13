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
requirements = python3==3.11.9,hostpython3==3.11.9,pygame-ce
# Fixamos o Python em 3.11.9 (em vez de deixar solto em "python3", que
# o python-for-android estava resolvendo para a versão 3.14, bem
# recente demais). Usamos o "pygame-ce" (não o "pygame" clássico),
# porque o pygame-ce é ativamente mantido e compatível com versões
# mais novas de header do Python/NDK — o pygame clássico tem uma
# receita desatualizada que quebra mesmo contra o Python 3.11 (erro
# de "longintrepr.h" não encontrado, um header interno do CPython que
# a receita antiga do pygame ainda espera encontrar).

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

# usa nossa receita própria do pygame-ce (na pasta p4a-recipes/), que
# corrige dois bugs conhecidos: (1) o python-for-android empacotando
# um binário compilado para o processador errado (x86_64 em vez de
# ARM), e (2) o Cython não sendo encontrado durante a compilação por
# ser instalado no ambiente Python errado.
p4a.local_recipes = ./p4a-recipes

[buildozer]
log_level = 2
warn_on_root = 1
