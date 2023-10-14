meson_cross_file_tmpl = """
[binaries]
c = '{CC}'
cpp = '{CXX}'
ar = '{AR}'
fortran = '{GFORTRAN}'
pkgconfig = 'pkg-config'

cmake = '{CMAKE}'
sdl2-config = ['emconfigure', 'sdl2-config']

[host_machine]
system = 'emscripten'
cpu_family = 'wasm32'
cpu = 'wasm'
endian = 'little'
"""
