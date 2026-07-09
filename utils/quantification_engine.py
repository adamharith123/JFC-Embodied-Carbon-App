import math


def quantify_sprinklers(inputs):
    """
    Quantify sprinkler system apparatus.
    """

    area = inputs["floor_area"]
    hazard = inputs["hazard"]

    spacing_lookup = {
        "Light Hazard": 21,
        "Ordinary Hazard": 12,
        "High Hazard": 9,
    }

    spacing = spacing_lookup.get(hazard, 12)

    sprinkler_heads = math.ceil(area / spacing)

    return {
        "spacing_area": spacing,
        "sprinkler_heads": sprinkler_heads,
    }
