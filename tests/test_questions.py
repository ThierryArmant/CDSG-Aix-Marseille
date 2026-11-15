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
    def test_memoire_ignore_les_faits_non_valides_et_sans_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/memoire.json').write_text(json.dumps({'entrees': [
                {'id': 'valide', 'statut': 'valide', 'verifie_le': '2026-11-15', 'texte': 'Fait sourcé', 'sources': [{'url': 'https://source.fr'}]},
                {'id': 'proposition', 'statut': 'a_verifier', 'verifie_le': '2026-11-15', 'texte': 'NE PAS INCLURE', 'sources': [{'url': 'https://source.fr'}]},
                {'id': 'sans-source', 'statut': 'valide', 'verifie_le': '2026-11-15', 'texte': 'NE PAS INCLURE', 'sources': []}
            ]}))
            with patch.object(app, 'RACINE', root):
                result = app.contexte_memoire()
            self.assertIn('Fait sourcé', result)
            self.assertNotIn('NE PAS INCLURE', result)

    def test_recherche_pdf_atteint_une_page_lointaine(self):
        texte = '\f'.join(['Sommaire général.'] * 35 + ['Les subventions et le financement du transport sont étudiés ici.'])
        result = app.passages_reference(texte, 'financement transport subventions')
        self.assertIn('[Page PDF 36]', result)
        self.assertIn('financement du transport', result)

    def test_catalogue_oriente_vers_les_guides_et_sources_de_financement(self):
        guides = app.references_question('memento vademecum créer une CDSG')
        financements = app.references_question('aides financières subventions transport')
        self.assertTrue(any('vade-mecum' in u for u in guides))
        self.assertTrue(any('/6060/' in u for u in financements))

    def test_dedoublonnage_preserve_rangs_dates_sources_et_evenements_distincts(self):
        base = {'type': 'distinction', 'date': None, 'source': 'https://source.fr'}
        es = [{**base, 'titre': '5ᵉ Prix Départemental – Devoir Collectif'},
              {**base, 'titre': '5e Prix Départemental – Devoir Collectif (concours de la Résistance)'},
              {**base, 'titre': '19e Prix Départemental – Devoir Individuel'},
              {**base, 'titre': '5e Prix Départemental – Devoir Collectif', 'date': '2025'}]
        result = app.elements_uniques(es)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(result[0]['variantes_fusionnees']), 1)
        self.assertEqual(len(es), 4)
        self.assertNotEqual(app.cle_element({'type': 'sortie', 'date': '2025-01-01', 'titre': 'Visite A'}),
                            app.cle_element({'type': 'sortie', 'date': '2025-01-01', 'titre': 'Visite B'}))

    def test_extraction_refuse_une_citation_de_la_fiche_absente_de_la_page(self):
        extraction = {'concerne': True, 'elements': [
            {'type': 'convention', 'titre': 'Convention', 'extrait': 'Convention signée en juin 2024 avec le régiment'},
            {'type': 'article', 'titre': 'Visite', 'extrait': 'Les élèves visitent la base aérienne'}]}
        page = {'url': 'https://source.fr', 'titre': 'Visite', 'texte': 'Les élèves visitent la base aérienne.', 'image': 'photo.jpg'}
        with patch.object(app, 'demander', return_value=extraction):
            result = app.analyser_page({}, page)
        self.assertEqual(len(result['elements']), 1)
        self.assertEqual(result['elements'][0]['image_nature'], 'illustration_article')

    def test_question_conserve_le_perimetre_et_ne_lance_pas_la_veille(self):
        question = 'Combien d’unités militaires dans le Vaucluse ?'
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(app, 'DOSSIER_REPONSES', Path(tmp)), \
                patch.object(app, 'references_question', return_value=[]), \
                patch.object(app, 'demander', side_effect=[{'requetes': ['unités Vaucluse site:defense.gouv.fr']}, {'lacunes': [], 'requetes': []}, 'Résultat à vérifier.\nFICHES: inconnu']), \
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

    def test_albert_transmet_une_lacune_aux_moteurs_et_conserve_la_trace(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(app, 'DOSSIER_REPONSES', Path(tmp)), \
                patch.object(app, 'references_question', return_value=[]), \
                patch.object(app, 'demander', side_effect=[{'requetes': []},
                    {'lacunes': ['Convention manquante'], 'requetes': ['convention officielle CDSG']},
                    'Convention confirmée [2].\nFICHES: ecole']), \
                patch.object(app, 'recherche_web', side_effect=[['https://source.fr/a'], ['https://source.fr/b']]) as search, \
                patch.object(app, 'lire_page', side_effect=lambda u, **kw: {'url': u, 'titre': 'Preuve', 'texte': 'preuve ' * 50}):
            app.question_web('Quelle convention ?', 'coordination',
                [{'id': 'ecole', 'etab': 'École', 'ville': 'Ville', 'dep': '84', 'statut': 'active'}], {})
            result = json.loads((Path(tmp) / 'coordination.json').read_text())
            self.assertEqual(search.call_args_list[1].args[0], 'convention officielle CDSG')
            self.assertEqual(len(result['sources']), 2)
            self.assertEqual(result['fiches'], ['ecole'])
            self.assertEqual(result['recherche'][1]['pages_lues'], 1)

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
