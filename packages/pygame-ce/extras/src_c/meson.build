# first the "required" modules

if plat == 'emscripten'
    time_src = 'void.c'
    _freetype_src = 'void.c'
    imageext_src = 'void.c'
    image_src = 'void.c'
    base_src = 'void.c'
    bufferproxy_src = 'void.c'
    color_src = 'void.c'
    display_src = 'void.c'
    draw_src = 'void.c'
    event_src = 'void.c'
    font_src = 'void.c'
    gfxdraw_src = 'void.c'
    joystick_src = 'void.c'
    key_src = 'void.c'
    newbuffer_src = 'void.c'
    mixer_music_src = 'void.c'
    mixer_src = 'void.c'
    mouse_src = 'void.c'
    pixelcopy_src = 'void.c'
    pixelarray_src = 'void.c'
    surface_src = 'void.c'
    surflock_src = 'void.c'
    rect_src = 'void.c'
    rwobject_src = 'void.c'
    system_src = 'void.c'
    window_src = 'void.c'
    geometry_src = 'void.c'
    transform_src = 'void.c'
    transform_objs = []
    constants_src = 'constants.c'
    mask_src = 'bitmask.c'
    math_src = 'math.c'
    simd_blitters_avx2_src = 'void.c'
    simd_blitters_sse2_src = 'void.c'
    simd_transform_avx2_src = 'void.c'
    simd_transform_sse2_src = 'void.c'
    simd_surface_fill_avx2_src = 'void.c'
    simd_surface_fill_sse2_src = 'void.c'

    static = py.extension_module(
        'static',
        'static.c',
        c_args: warnings_error,
        dependencies: pg_base_deps,
        install: true,
        subdir: pg,
    )
else
    time_src = 'time.c'
    _freetype_src = [
        'freetype/ft_cache.c',
        'freetype/ft_wrap.c',
        'freetype/ft_render.c',
        'freetype/ft_render_cb.c',
        'freetype/ft_layout.c',
        'freetype/ft_unicode.c',
        '_freetype.c',
    ]
    imageext_src = 'imageext.c'
    image_src = 'image.c'
    base_src = 'base.c'
    bufferproxy_src = 'bufferproxy.c'
    color_src = 'color.c'
    display_src = 'display.c'
    draw_src = 'draw.c'
    event_src = 'event.c'
    font_src = 'font.c'
    gfxdraw_src = ['gfxdraw.c', 'SDL_gfx/SDL_gfxPrimitives.c']
    joystick_src = 'joystick.c'
    key_src = 'key.c'
    newbuffer_src = 'newbuffer.c'
    mixer_music_src = 'music.c'
    mixer_src = 'mixer.c'
    mouse_src = 'mouse.c'
    pixelcopy_src = 'pixelcopy.c'
    pixelarray_src = 'pixelarray.c'
    surface_src = [
        'surface.c',
        'alphablit.c',
        'surface_fill.c',
    ]
    surflock_src = 'surflock.c'
    rect_src = ['rect.c', 'pgcompat_rect.c']
    rwobject_src = 'rwobject.c'
    system_src = 'system.c'
    window_src = 'window.c'
    geometry_src = 'geometry.c'
    constants_src = 'constants.c'
    mask_src = ['mask.c', 'bitmask.c']
    math_src = 'math.c'
    simd_blitters_avx2_src = 'simd_blitters_avx2.c'
    simd_blitters_sse2_src = 'simd_blitters_sse2.c'
    simd_transform_avx2_src = 'simd_transform_avx2.c'
    simd_transform_sse2_src = 'simd_transform_sse2.c'
    simd_surface_fill_avx2_src = 'simd_surface_fill_avx2.c'
    simd_surface_fill_sse2_src = 'simd_surface_fill_sse2.c'

    # TODO: support SDL3
    if sdl_api != 3
    transform_src = ['transform.c', 'rotozoom.c', 'scale2x.c']
    transform_objs = []

    if (
        cc.get_argument_syntax() == 'msvc'
        and host_machine.cpu_family().startswith('x86')
    )
        if host_machine.cpu_family() == 'x86'
            transform_objs += '../buildconfig/obj/win32/scale_mmx.obj'
        else
            transform_objs += '../buildconfig/obj/win64/scale_mmx.obj'
        endif
    else
        transform_src += 'scale_mmx.c'
    endif

    endif  # sdl_api != 3

endif

base = py.extension_module(
    'base',
    base_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

color = py.extension_module(
    'color',
    color_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

constants = py.extension_module(
    'constants',
    constants_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# TODO: support SDL3
if sdl_api != 3
display = py.extension_module(
    'display',
    display_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif

event = py.extension_module(
    'event',
    event_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

key = py.extension_module(
    'key',
    key_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

mouse = py.extension_module(
    'mouse',
    mouse_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

rect = py.extension_module(
    'rect',
    rect_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

rwobject = py.extension_module(
    'rwobject',
    rwobject_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# TODO: support SDL3
if sdl_api != 3
simd_blitters_avx2 = static_library(
    'simd_blitters_avx2',
    simd_blitters_avx2_src,
    dependencies: pg_base_deps,
    c_args: simd_avx2_flags + warnings_error,
)

simd_blitters_sse2 = static_library(
    'simd_blitters_sse2',
    simd_blitters_sse2_src,
    dependencies: pg_base_deps,
    c_args: simd_sse2_neon_flags + warnings_error,
)

simd_surface_fill_avx2 = static_library(
    'simd_surface_fill_avx2',
    simd_surface_fill_avx2_src,
    dependencies: pg_base_deps,
    c_args: simd_avx2_flags + warnings_error,
)

simd_surface_fill_sse2 = static_library(
    'simd_surface_fill_sse2',
    simd_surface_fill_sse2_src,
    dependencies: pg_base_deps,
    c_args: simd_sse2_neon_flags + warnings_error,
)

surface = py.extension_module(
    'surface',
    surface_src,
    c_args: warnings_error,
    link_with: [
        simd_blitters_avx2,
        simd_blitters_sse2,
        simd_surface_fill_avx2,
        simd_surface_fill_sse2,
    ],
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif

# TODO: support SDL3
surflock = py.extension_module(
    'surflock',
    surflock_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

time = py.extension_module(
    'time',
    time_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# TODO: support SDL3
if sdl_api != 3
joystick = py.extension_module(
    'joystick',
    joystick_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif


# TODO: support SDL3
if sdl_api != 3
draw = py.extension_module(
    'draw',
    draw_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif

image = py.extension_module(
    'image',
    image_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# TODO: support SDL3
if sdl_api != 3

simd_transform_avx2 = static_library(
    'simd_transform_avx2',
    simd_transform_avx2_src,
    dependencies: pg_base_deps,
    c_args: simd_avx2_flags + warnings_error,
)

simd_transform_sse2 = static_library(
    'simd_transform_sse2',
    simd_transform_sse2_src,
    dependencies: pg_base_deps,
    c_args: simd_sse2_neon_flags + warnings_error,
)

transform = py.extension_module(
    'transform',
    transform_src,
    c_args: warnings_error,
    link_with: [simd_transform_avx2, simd_transform_sse2],
    objects: transform_objs,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif

mask = py.extension_module(
    'mask',
    mask_src,
    c_args: warnings_error + warnings_temp_mask,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

bufferproxy = py.extension_module(
    'bufferproxy',
    bufferproxy_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# TODO: support SDL3
if sdl_api != 3
pixelarray = py.extension_module(
    'pixelarray',
    pixelarray_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif

math = py.extension_module(
    'math',
    math_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

pixelcopy = py.extension_module(
    'pixelcopy',
    pixelcopy_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

newbuffer = py.extension_module(
    'newbuffer',
    newbuffer_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# new/experimental/uncommon stuff, but built by default
system = py.extension_module(
    'system',
    system_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

geometry = py.extension_module(
    'geometry',
    geometry_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

window = py.extension_module(
    'window',
    window_src,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)

# TODO: support SDL3
if sdl_api != 3
gfxdraw = py.extension_module(
    'gfxdraw',
    gfxdraw_src,
    # c_args: warnings_error,
    dependencies: pg_base_deps,
    install: true,
    subdir: pg,
)
endif

# pygame._sdl2
# TODO: support SDL3
if sdl_api != 3
subdir('_sdl2')
endif

# pygame._camera

# TODO: support SDL3
if sdl_api != 3 and plat != 'emscripten'
pg_camera_sources = ['_camera.c']
pg_camera_link = []
if plat == 'win'
    pg_camera_sources += 'camera_windows.c'
    # TODO: should this link logic be improved/made meson-ey?
    pg_camera_link = []
    foreach link_arg : [
        '-lMfplat',
        '-lMf',
        '-lMfuuid',
        '-lMfreadwrite',
        '-lOle32',
    ]
        if cc.has_link_argument(link_arg)
            pg_camera_link += link_arg
        endif
    endforeach
elif plat == 'linux'
    pg_camera_sources += 'camera_v4l2.c'
endif

_camera = py.extension_module(
    '_camera',
    pg_camera_sources,
    c_args: warnings_error,
    dependencies: pg_base_deps,
    link_args: pg_camera_link,
    install: true,
    subdir: pg,
)
endif

# pygame.scrap

# TODO: support SDL3
if sdl_api != 3 and plat != 'emscripten'
pg_scrap_link = [] # TODO: should this link logic be improved/made meson-ey?
if plat == 'win'
    pg_scrap_link += ['-luser32', '-lgdi32']
endif

scrap = py.extension_module(
    'scrap',
    'scrap.c',
    c_args: warnings_error,
    dependencies: pg_base_deps,
    link_args: pg_scrap_link,
    install: true,
    subdir: pg,
)
endif

# optional modules

if sdl_image_dep.found()
    imageext = py.extension_module(
        'imageext',
        imageext_src,
        c_args: warnings_error,
        dependencies: pg_base_deps + sdl_image_dep,
        install: true,
        subdir: pg,
    )
endif

# TODO: support SDL3
if sdl_api != 3

if sdl_ttf_dep.found()
    font = py.extension_module(
        'font',
        font_src,
        c_args: warnings_error,
        dependencies: pg_base_deps + sdl_ttf_dep,
        install: true,
        subdir: pg,
    )
endif

if sdl_mixer_dep.found()
    mixer = py.extension_module(
        'mixer',
        mixer_src,
        c_args: warnings_error,
        dependencies: pg_base_deps + sdl_mixer_dep,
        install: true,
        subdir: pg,
    )

    mixer_music = py.extension_module(
        'mixer_music',
        mixer_music_src,
        c_args: warnings_error,
        dependencies: pg_base_deps + sdl_mixer_dep,
        install: true,
        subdir: pg,
    )
endif

if freetype_dep.found()
    _freetype = py.extension_module(
        '_freetype',
        _freetype_src,
        c_args: warnings_error + warnings_temp_freetype,
        dependencies: pg_base_deps + freetype_dep,
        install: true,
        subdir: pg,
    )
endif

endif

if portmidi_dep.found() and get_option('midi').enabled()
    pypm = py.extension_module(
        'pypm',
        fs.is_file('pypm.c') ? 'pypm.c' : 'cython/pygame/pypm.pyx',
        # c_args: warnings_error,
        dependencies: pg_base_deps + portmidi_deps,
        install: true,
        subdir: pg,
    )
endif
