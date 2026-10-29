import unittest

from resources.lib.show_hierarchy import show_detail_items


def episode(episode_id, season_number, episode_number):
    return {
        "id": episode_id,
        "title": "Episode {}".format(episode_number),
        "episodeNumber": episode_number,
        "seasonNumber": season_number,
    }


class ShowHierarchyTests(unittest.TestCase):

    def setUp(self):
        self.show = {
            "id": "show-1",
            "libraryId": "library-1",
            "title": "Example Show",
            "seasons": [
                {
                    "seasonNumber": 2,
                    "episodes": [
                        episode("s2e2", 2, 2),
                        episode("s2e1", 2, 1),
                    ],
                },
                {
                    "seasonNumber": 0,
                    "episodes": [episode("special-1", 0, 1)],
                },
                {
                    "seasonNumber": 1,
                    "episodes": [episode("s1e1", 1, 1)],
                },
            ],
        }

    def test_builds_sorted_season_folders(self):
        items = show_detail_items(self.show, {"media_type": "Series"})

        self.assertEqual([item["seasonNumber"] for item in items], [0, 1, 2])
        self.assertEqual([item["title"] for item in items],
                         ["Specials", "Season 01", "Season 02"])
        self.assertTrue(all(item["type"] == "Season" for item in items))
        self.assertTrue(all(item["seriesId"] == "show-1" for item in items))
        self.assertTrue(all(item["libraryId"] == "library-1" for item in items))

    def test_filters_and_orders_one_season(self):
        items = show_detail_items(
            self.show, {"media_type": "Season", "season_number": "2"})

        self.assertEqual([item["id"] for item in items], ["s2e1", "s2e2"])
        self.assertTrue(all(item["type"] == "Episode" for item in items))
        self.assertTrue(all(item["seriesTitle"] == "Example Show" for item in items))
        self.assertTrue(all(item["libraryId"] == "library-1" for item in items))

    def test_all_episodes_sort_by_season_then_episode(self):
        items = show_detail_items(
            self.show, {"media_type": "Season", "season_number": "-1"})

        self.assertEqual([item["id"] for item in items],
                         ["special-1", "s1e1", "s2e1", "s2e2"])

    def test_unknown_season_returns_no_episodes(self):
        items = show_detail_items(
            self.show, {"media_type": "Season", "season_number": "99"})

        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
