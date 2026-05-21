from dataclasses import dataclass


@dataclass(frozen=True)
class UploadDesign:
    allowed_extensions: frozenset[str] = frozenset({'png', 'jpg', 'jpeg', 'webp', 'gif', 'pdf'})
    image_extensions: frozenset[str] = frozenset({'png', 'jpg', 'jpeg', 'webp', 'gif'})
    allowed_mime_types: frozenset[str] = frozenset({
        'image/png',
        'image/jpeg',
        'image/webp',
        'image/gif',
        'application/pdf',
    })


@dataclass(frozen=True)
class GardenDesign:
    trash_location_name: str = 'Papierkorb'
    default_location_color: str = '#2f6d40'


@dataclass(frozen=True)
class TimelineDesign:
    event_type_map: dict[str, str] = None
    system_event_templates: dict[str, dict[str, str]] = None
    planting_state_types: dict[str, str] = None

    def __post_init__(self):
        object.__setattr__(self, 'event_type_map', {
            'planting': 'plant_event',
            'outplant': 'plant_event',
            'transplant': 'plant_event',
            'user_comment': 'user_event',
            'care_event': 'care_event',
            'measurement': 'measurement_event',
        })
        object.__setattr__(self, 'system_event_templates', {
            'planting': {'title': 'Eingepflanzt', 'description': 'Pflanze wurde eingepflanzt.'},
            'transplant': {'title': 'Umgepflanzt', 'description': 'Pflanze wurde umgepflanzt.'},
            'outplant': {'title': 'Ausgepflanzt', 'description': 'Pflanze wurde ausgepflanzt.'},
        })
        object.__setattr__(self, 'planting_state_types', {
            'Eingepflanzt': 'planting',
            'Umgepflanzt': 'transplant',
            'Ausgepflanzt': 'outplant',
        })


UPLOAD_DESIGN = UploadDesign()
GARDEN_DESIGN = GardenDesign()
TIMELINE_DESIGN = TimelineDesign()
