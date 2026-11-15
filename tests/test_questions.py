import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('veille', Path(__file__).parents[1] / 'recherche/recherche_web.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class QuestionsTests(unittest.TestCase):
    def test_question_conserve_le_perimetre_et_ne_lance_pas_la_veille(self):
        question = 'Combien d’unités militaires dans le Vaucluse ?'
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(app, 'DOSSIER_REPONSES', Path(tmp)), \
                patch.object(app, 'demander', side_effect=[{'requetes': ['unités Vaucluse site:defense.gouv.fr']}, 'Résultat à vérifier.\nFICHES: inconnu']), \
                patch.object(app, 'recherche_web', return_value=['https://exemple.fr']) as search, \
                patch.object(app, 'lire_page', return_value={'url': 'https://exemple.fr', 'titre': 'Unités', 'texte': 'a' * 200}), \
                patch.object(app, 'fiches_citees') as enrichir, \
                patch.object(app, 'ecrire_resumes'), patch.object(app, 'ecrire_actualites'):
            app.question_web(question, 'test', [], {})
            self.assertEqual(search.call_args_list[0].args[0], question)
            enrichir.assert_not_called()
            result = json.loads((Path(tmp) / 'test.json').read_text())
            self.assertEqual(result['fiches'], [])
            self.assertEqual(len(result['sources']), 1)
            self.assertNotIn('FICHES:', result['reponse'])

    def test_absence_de_cle_produit_un_resultat_explicite(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, 'DOSSIER_REPONSES', Path(tmp)), \
                patch.object(app, 'CLE', None), \
                patch('sys.argv', ['recherche_web.py', '--question-web', 'Question', '--qid', 'sans-cle']):
            with self.assertRaises(SystemExit):
                app.main()
            result = json.loads((Path(tmp) / 'sans-cle.json').read_text())
            self.assertEqual(result['erreur'], 'cle_absente')

    def test_erreur_du_modele_est_enregistree_sans_secret(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, 'DOSSIER_REPONSES', Path(tmp)), \
                patch.object(app, 'CLE', 'cle-test'), patch.object(app, 'lire_classes', return_value=[]), \
                patch.object(app, 'lire_resumes', return_value={}), \
                patch.object(app, 'question_web', side_effect=RuntimeError('NE-PAS-PUBLIER')), \
                patch('sys.argv', ['recherche_web.py', '--question-web', 'Question', '--qid', 'erreur']):
            with self.assertRaises(RuntimeError):
                app.main()
            result = (Path(tmp) / 'erreur.json').read_text()
            self.assertEqual(json.loads(result)['erreur'], 'service_indisponible')
            self.assertNotIn('NE-PAS-PUBLIER', result)


if __name__ == '__main__':
    unittest.main()
