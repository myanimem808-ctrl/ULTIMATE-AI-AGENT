import unittest
from ultimate_agent.youtube import validate_youtube_url


class YouTubeURLTests(unittest.TestCase):
    def test_accepts_youtube_video_links(self):
        self.assertEqual(validate_youtube_url("https://www.youtube.com/watch?v=abc"), "https://www.youtube.com/watch?v=abc")
        self.assertEqual(validate_youtube_url("https://youtu.be/abc"), "https://youtu.be/abc")

    def test_rejects_non_youtube_and_lookalike_hosts(self):
        for url in (
            "https://example.com/watch?v=abc",
            "https://youtube.com.evil.example/watch?v=abc",
            "file:///C:/users/video.mp4",
            "javascript:alert(1)",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_youtube_url(url)


if __name__ == "__main__":
    unittest.main()
