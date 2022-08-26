import base64
import pathlib

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
SAMPLE_IMAGE = base64.b64encode(
    (DEMO_PATH / "tree-with-transparency.heic").read_bytes()
)


def test_read(selenium):
    selenium.load_package(["Pillow", "pillow_heif"])
    selenium.run(
        f"""
        import base64
        with open("tree-with-transparency.heic", "wb") as f:
            f.write(base64.b64decode({SAMPLE_IMAGE!r}))

        from PIL import Image
        from pillow_heif import register_heif_opener

        register_heif_opener()

        im = Image.open("tree-with-transparency.heic")
        im = im.rotate(13)
        im.save(f"rotated_image.heic", quality=90)
        """
    )
