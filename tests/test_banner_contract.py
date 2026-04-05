import json
import unittest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "banner"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


class BannerContractFixturesTests(unittest.TestCase):
    def test_terms_fixture_captures_expected_contract(self) -> None:
        fixture = _load_fixture("terms")

        self.assertEqual(fixture["request"]["method"], "GET")
        self.assertEqual(fixture["request"]["path"], "/StudentSelfService/studentGrades/term")
        self.assertEqual(fixture["request"]["query"], {"max": "200", "page": "1"})
        self.assertEqual(fixture["response"]["status"], 200)
        self.assertIsInstance(fixture["response"]["body"], list)
        self.assertEqual(fixture["response"]["body"][0]["code"], "-1")

    def test_levels_fixture_captures_expected_contract(self) -> None:
        fixture = _load_fixture("levels")

        self.assertEqual(fixture["request"]["method"], "GET")
        self.assertEqual(fixture["request"]["path"], "/StudentSelfService/studentGrades/level")
        self.assertEqual(fixture["request"]["query"]["term"], "202610")
        self.assertEqual(fixture["response"]["status"], 200)
        self.assertEqual(fixture["response"]["body"][0]["code"], "PR")

    def test_courses_fixture_captures_expected_contract(self) -> None:
        fixture = _load_fixture("courses")
        query = fixture["request"]["query"]
        body = fixture["response"]["body"]

        self.assertEqual(fixture["request"]["method"], "GET")
        self.assertEqual(fixture["request"]["path"], "/StudentSelfService/studentGrades/courses")
        self.assertEqual(query["termCode"], "202610")
        self.assertEqual(query["levelCode"], "PR")
        self.assertEqual(query["filterText"], "")
        self.assertEqual(query["pageOffset"], "0")
        self.assertEqual(query["pageMaxSize"], "200")
        self.assertEqual(query["sortColumn"], "-1")
        self.assertEqual(query["sortDirection"], "-1")
        self.assertEqual(fixture["request"]["headers"]["x-requested-with"], "XMLHttpRequest")
        self.assertTrue(body["success"])
        self.assertEqual(body["totalCount"], len(body["data"]))
        self.assertIn("courseReferenceNumber", body["data"][0])
        self.assertIn("gradeDetailDisplayInd", body["data"][0])

    def test_components_fixture_captures_expected_contract(self) -> None:
        fixture = _load_fixture("components")
        query = fixture["request"]["query"]
        body = fixture["response"]["body"]

        self.assertEqual(fixture["request"]["method"], "GET")
        self.assertEqual(fixture["request"]["path"], "/StudentSelfService/componentDetails/componentDetails")
        self.assertEqual(query["selectedTerm"], "202510")
        self.assertEqual(query["selectedCrn"], "12346")
        self.assertEqual(query["filterText"], "")
        self.assertEqual(query["pageOffset"], "0")
        self.assertEqual(query["pageMaxSize"], "200")
        self.assertEqual(query["sortColumn"], "name")
        self.assertEqual(query["sortDirection"], "asc")
        self.assertTrue(body["success"])
        self.assertEqual(body["totalCount"], len(body["data"]))
        self.assertTrue(any(item["mustPass"] for item in body["data"]))
        self.assertTrue(any(item["hasSubComponents"] for item in body["data"]))

    def test_subcomponents_fixture_captures_expected_contract(self) -> None:
        fixture = _load_fixture("subcomponents")
        query = fixture["request"]["query"]
        body = fixture["response"]["body"]

        self.assertEqual(fixture["request"]["method"], "GET")
        self.assertEqual(fixture["request"]["path"], "/StudentSelfService/componentDetails/subComponentDetails")
        self.assertEqual(query["selectedTerm"], "202510")
        self.assertEqual(query["selectedCrn"], "12346")
        self.assertEqual(query["selectedComponentId"], "70004")
        self.assertEqual(query["sortColumn"], "name")
        self.assertEqual(query["sortDirection"], "asc")
        self.assertTrue(body["success"])
        self.assertGreater(len(body["data"]), 0)
        self.assertTrue(all(not item["isComponent"] for item in body["data"]))


if __name__ == "__main__":
    unittest.main()
