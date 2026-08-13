"""
Receita customizada para compilar o pygame-ce corretamente para
Android (arquitetura ARM), evitando dois bugs conhecidos:

1) O python-for-android empacotando um binário compilado para
   x86_64 em vez de compilar de verdade para o processador do
   celular (erro: "dlopen failed: ... is for EM_X86_64 instead of
   EM_AARCH64").

2) O passo de build do pygame-ce reclamando "You need cython" mesmo
   com o cython instalado — porque ele é instalado no ambiente
   Python errado (o do PACOTE do app, não o Python que efetivamente
   RODA o script de build). Aqui garantimos explicitamente que o
   Cython esteja disponível para esse Python específico antes de
   compilar.
"""
from os.path import join

import sh
from pythonforandroid.logger import shprint
from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory


class PygameCERecipe(CompiledComponentsPythonRecipe):
    version = "2.5.0"
    url = "https://github.com/pygame-community/pygame-ce/archive/refs/tags/{version}.tar.gz"

    site_packages_name = "pygame-ce"
    name = "pygame-ce"

    depends = [
        "sdl2",
        "sdl2_image",
        "sdl2_mixer",
        "sdl2_ttf",
        "setuptools",
        "jpeg",
        "png",
    ]
    call_hostpython_via_targetpython = False  # por causa do setuptools
    install_in_hostpython = False

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)

        # Garante que o Cython esteja instalado no MESMO interpretador
        # Python que vai rodar "setup.py build_ext" (o hostpython de
        # build, não o Python de destino do app).
        hostpython = sh.Command(self.ctx.hostpython)
        shprint(hostpython, "-m", "pip", "install", "-q", "cython==0.29.36", _tail=20)

        with current_directory(self.get_build_dir(arch.arch)):
            setup_template = open(join("buildconfig", "Setup.Android.SDL2.in")).read()
            env = self.get_recipe_env(arch)
            env["ANDROID_ROOT"] = join(self.ctx.ndk.sysroot, "usr")

            png = self.get_recipe("png", self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), ".libs")
            png_inc_dir = png.get_build_dir(arch)

            jpeg = self.get_recipe("jpeg", self.ctx)
            jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            sdl_mixer_includes = ""
            sdl2_mixer_recipe = self.get_recipe("sdl2_mixer", self.ctx)
            for include_dir in sdl2_mixer_recipe.get_include_dirs(arch):
                sdl_mixer_includes += f"-I{include_dir} "

            setup_file = setup_template.format(
                sdl_includes=(
                    " -I"
                    + join(self.ctx.bootstrap.build_dir, "jni", "SDL", "include")
                    + " -L"
                    + join(self.ctx.bootstrap.build_dir, "libs", str(arch))
                    + " -L"
                    + png_lib_dir
                    + " -L"
                    + jpeg_lib_dir
                    + " -L"
                    + arch.ndk_lib_dir_versioned
                ),
                sdl_ttf_includes="-I"
                + join(self.ctx.bootstrap.build_dir, "jni", "SDL2_ttf"),
                sdl_image_includes="-I"
                + join(self.ctx.bootstrap.build_dir, "jni", "SDL2_image", "include"),
                sdl_mixer_includes=sdl_mixer_includes,
                jpeg_includes="-I" + jpeg_inc_dir,
                png_includes="-I" + png_inc_dir,
                freetype_includes="",
            )
            open("Setup", "w").write(setup_file)

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env["USE_SDL2"] = "1"
        env["PYGAME_CROSS_COMPILE"] = "TRUE"
        env["PYGAME_ANDROID"] = "TRUE"
        return env


recipe = PygameCERecipe()
