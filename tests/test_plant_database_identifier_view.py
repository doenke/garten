import os
import tempfile
import unittest

os.environ.setdefault('SECRET_KEY', 'x' * 40)

from app import create_app
from app.models import Location, Plant, PlantDatabaseIdentifier, User, db


class PlantDatabaseIdentifierViewTest(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.sqlite')
        os.close(self.db_fd)
        os.environ['DATABASE_URL'] = f'sqlite:///{self.db_path}'
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

        with self.app.app_context():
            self.user = User(sub='test-user', name='Test User')
            db.session.add(self.user)
            db.session.flush()
            self.location = Location(name='Beet', user_id=self.user.id, creator_id=self.user.id)
            db.session.add(self.location)
            db.session.flush()
            self.plant = Plant(name='Brunnera', location_id=self.location.id, creator_id=self.user.id)
            self.plant.database_identifiers = [
                PlantDatabaseIdentifier(
                    catalog_key='wikipedia_de',
                    taxonomy_id='Gro%C3%9Fbl%C3%A4ttriges_Kaukasusvergissmeinnicht',
                ),
            ]
            db.session.add(self.plant)
            db.session.commit()
            self.user_id = self.user.id
            self.location_id = self.location.id
            self.plant_id = self.plant.id

        with self.client.session_transaction() as session:
            session['user_id'] = self.user_id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.unlink(self.db_path)
        os.environ.pop('DATABASE_URL', None)

    def test_wikipedia_identifier_is_decoded_for_display(self):
        response = self.client.get(f'/plants/{self.plant_id}')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('value="Großblättriges_Kaukasusvergissmeinnicht"', html)
        self.assertIn('title="Deutsche Wikipedia (Großblättriges_Kaukasusvergissmeinnicht)"', html)
        self.assertNotIn('Gro%C3%9Fbl%C3%A4ttriges_Kaukasusvergissmeinnicht)', html)

    def test_wikipedia_identifier_is_saved_as_readable_slug(self):
        response = self.client.post(
            f'/plants/{self.plant_id}/masterdata',
            data={
                'name': 'Brunnera',
                'location_id': str(self.location_id),
                'database_id_wikipedia_de': 'Gro%C3%9Fbl%C3%A4ttriges Kaukasusvergissmeinnicht',
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            identifier = PlantDatabaseIdentifier.query.filter_by(
                plant_id=self.plant_id,
                catalog_key='wikipedia_de',
            ).one()
            self.assertEqual(identifier.taxonomy_id, 'Großblättriges_Kaukasusvergissmeinnicht')


if __name__ == '__main__':
    unittest.main()
