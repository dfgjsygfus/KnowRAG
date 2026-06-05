import unittest

from backend.app.schemas.query_routing import QueryIntent
from backend.app.services.query_router import route_query


class QueryRouterTest(unittest.IsolatedAsyncioTestCase):
    async def test_routes_greeting_to_casual_chat_without_model(self):
        classifier = FakeClassifier()

        route = await route_query("你好", classifier=classifier)

        self.assertEqual(route.intent, QueryIntent.CASUAL_CHAT)
        self.assertEqual(route.method, "rule")
        self.assertEqual(classifier.questions, [])

    async def test_routes_explicit_knowledge_question_without_model(self):
        classifier = FakeClassifier()

        route = await route_query("ChiefArchitect 的职责是什么？", classifier=classifier)

        self.assertEqual(route.intent, QueryIntent.KNOWLEDGE_QUERY)
        self.assertEqual(route.method, "rule")
        self.assertEqual(classifier.questions, [])

    async def test_uses_model_for_ambiguous_question(self):
        classifier = FakeClassifier(
            '{"intent":"casual_chat","confidence":0.92,"reason":"用户在表达个人感受"}'
        )

        route = await route_query("今天感觉不错", classifier=classifier)

        self.assertEqual(route.intent, QueryIntent.CASUAL_CHAT)
        self.assertEqual(route.method, "model")
        self.assertEqual(classifier.questions, ["今天感觉不错"])

    async def test_low_confidence_model_result_defaults_to_knowledge_query(self):
        classifier = FakeClassifier(
            '{"intent":"casual_chat","confidence":0.40,"reason":"不确定"}'
        )

        route = await route_query("帮我看看这个", classifier=classifier, min_confidence=0.65)

        self.assertEqual(route.intent, QueryIntent.KNOWLEDGE_QUERY)
        self.assertEqual(route.method, "fallback")

    async def test_model_error_defaults_to_knowledge_query(self):
        classifier = FakeClassifier(error=RuntimeError("provider unavailable"))

        route = await route_query("帮我看看这个", classifier=classifier)

        self.assertEqual(route.intent, QueryIntent.KNOWLEDGE_QUERY)
        self.assertEqual(route.method, "fallback")


class FakeClassifier:
    def __init__(self, response="", error=None):
        self.response = response
        self.error = error
        self.questions = []

    async def classify(self, question):
        self.questions.append(question)
        if self.error:
            raise self.error
        return self.response


if __name__ == "__main__":
    unittest.main()
