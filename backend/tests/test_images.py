import io

from PIL import Image

from app.config import get_settings


def image_bytes():
    image = Image.new("RGB", (2000, 1000), "orange")
    exif = Image.Exif()
    exif[0x010E] = "private metadata"
    output = io.BytesIO()
    image.save(output, "JPEG", exif=exif)
    return output.getvalue()


def upload(client, owner, card, data, name="picture.jpg"):
    return client.post(f"/api/flashcards/cards/{card['id']}/images?side=front", headers=owner,
                       files={"file": (name, data, "image/jpeg")})


def test_image_validation(client, owner, card):
    assert upload(client, owner, card, b"not an image", "renamed.jpg").status_code == 422
    assert upload(client, owner, card, b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image.svg").status_code == 422
    settings = get_settings()
    previous = settings.max_image_bytes
    settings.max_image_bytes = 20
    try:
        assert upload(client, owner, card, b"x" * 21).status_code == 413
    finally:
        settings.max_image_bytes = previous


def test_metadata_resize_ownership_and_cleanup(client, owner, other, card):
    response = upload(client, owner, card, image_bytes())
    assert response.status_code == 201
    image_id = response.json()["id"]
    path = f"/api/flashcards/cards/{card['id']}/images/{image_id}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=other).status_code == 404
    assert client.delete(path, headers=other).status_code == 404
    response = client.get(path, headers=owner)
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (1600, 800)
        assert not image.getexif()
        assert image.format == "WEBP"
    assert len(list(get_settings().media_dir.iterdir())) == 1
    assert client.delete(path, headers=owner).status_code == 200
    assert not list(get_settings().media_dir.iterdir())


def test_deduplication_and_card_deletion(client, owner, deck, card):
    other_card = client.post(f"/api/flashcards/decks/{deck['id']}/cards", headers=owner,
                            json={"front": "Another", "back": "Answer"}).json()
    assert upload(client, owner, card, image_bytes()).status_code == 201
    assert upload(client, owner, other_card, image_bytes()).status_code == 201
    assert len(list(get_settings().media_dir.iterdir())) == 1
    assert client.delete(f"/api/flashcards/cards/{card['id']}", headers=owner).status_code == 200
    assert len(list(get_settings().media_dir.iterdir())) == 1
    assert client.delete(f"/api/flashcards/decks/{deck['id']}", headers=owner).status_code == 200
    assert not list(get_settings().media_dir.iterdir())


def test_upload_ownership_and_image_limit(client, owner, other, card):
    assert upload(client, other, card, image_bytes()).status_code == 404
    settings = get_settings()
    previous = settings.max_images_per_card
    settings.max_images_per_card = 1
    try:
        assert upload(client, owner, card, image_bytes()).status_code == 201
        assert upload(client, owner, card, image_bytes()).status_code == 422
    finally:
        settings.max_images_per_card = previous
