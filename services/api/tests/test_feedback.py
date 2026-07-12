import json
from unittest import mock

import pytest
from django.test import RequestFactory
from ninja.errors import HttpError

from scraping.models import Feedback
from scraping.tasks import notify_feedback
from scraping.throttling import resolve_jwt_user
from tests.factories import FeedbackFactory


@pytest.mark.django_db
class TestResolveJwtUser:
    def test_no_token_is_anonymous(self):
        request = RequestFactory().post("/v1/feedback")
        assert resolve_jwt_user(request, strict=True) is None
        assert resolve_jwt_user(request, strict=False) is None

    def test_bad_token_raises_when_strict(self):
        request = RequestFactory().post("/v1/feedback", HTTP_AUTHORIZATION="Bearer nope")
        with pytest.raises(HttpError):
            resolve_jwt_user(request, strict=True)

    def test_bad_token_is_anonymous_when_not_strict(self):
        request = RequestFactory().post("/v1/feedback", HTTP_AUTHORIZATION="Bearer nope")
        assert resolve_jwt_user(request, strict=False) is None


def _on_commit_inline():
    # django_db wraps each test in a transaction that never commits, so
    # transaction.on_commit callbacks never fire. Run them inline instead.
    return mock.patch("scraping.api.transaction.on_commit", side_effect=lambda fn: fn())


@pytest.mark.django_db
class TestSubmitFeedback:
    def test_anonymous_submission_is_stored(self, client):
        with _on_commit_inline(), mock.patch("scraping.api.notify_feedback.delay") as notify:
            response = client.post(
                "/v1/feedback",
                json={"message": "  Love it  ", "platform": "ios", "locale": "nl", "app_version": "1.4.0"},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["created_at"]

        feedback = Feedback.objects.get(pk=body["id"])
        assert feedback.user is None
        assert feedback.message == "Love it"  # trimmed
        assert feedback.platform == "ios"
        assert feedback.locale == "nl"
        assert feedback.app_version == "1.4.0"
        notify.assert_called_once_with(feedback.pk)

    def test_authenticated_submission_attributes_the_user(self, client, user_headers, test_user):
        with _on_commit_inline(), mock.patch("scraping.api.notify_feedback.delay"):
            response = client.post("/v1/feedback", json={"message": "Signed-in feedback"}, headers=user_headers)

        assert response.status_code == 201
        feedback = Feedback.objects.get(pk=response.json()["id"])
        assert feedback.user == test_user

    def test_malformed_token_is_rejected(self, client):
        with mock.patch("scraping.api.notify_feedback.delay"):
            response = client.post(
                "/v1/feedback",
                json={"message": "hi"},
                headers={"AUTHORIZATION": "Bearer not-a-jwt"},
            )

        assert response.status_code == 401
        assert Feedback.objects.count() == 0

    @pytest.mark.parametrize(
        "payload",
        [
            {"message": "   "},
            {"message": ""},
            {"message": "x" * 5001},
            {"message": "ok", "platform": "windows"},
            {"message": "ok", "locale": "de"},
        ],
    )
    def test_invalid_body_returns_422(self, client, payload):
        with mock.patch("scraping.api.notify_feedback.delay"):
            response = client.post("/v1/feedback", json=payload)

        assert response.status_code == 422
        assert Feedback.objects.count() == 0


@pytest.mark.django_db
class TestNotifyFeedback:
    def test_posts_to_webhook_when_configured(self, settings, respx_mock):
        settings.MATTERMOST_FEEDBACK_WEBHOOK_URL = "https://mm.example.com/hooks/abc"
        route = respx_mock.post("https://mm.example.com/hooks/abc").respond(200)
        feedback = FeedbackFactory(message="Ship it")

        notify_feedback(feedback.pk)  # ty: ignore[unresolved-attribute]

        assert route.called
        sent = json.loads(route.calls.last.request.content)
        assert "Ship it" in sent["text"]

    def test_untrusted_message_is_fenced(self, settings, respx_mock):
        settings.MATTERMOST_FEEDBACK_WEBHOOK_URL = "https://mm.example.com/hooks/abc"
        route = respx_mock.post("https://mm.example.com/hooks/abc").respond(200)
        feedback = FeedbackFactory(message="hey @channel ``` please look")

        notify_feedback(feedback.pk)  # ty: ignore[unresolved-attribute]

        text = json.loads(route.calls.last.request.content)["text"]
        # The raw body is fenced so @channel can't ping and its backticks can't
        # break out of the block.
        body = text.split("from anonymous\n", 1)[1]
        fence = body.split("\n", 1)[0]
        assert fence.startswith("````")  # longer than the ``` inside the message
        assert body == f"{fence}\nhey @channel ``` please look\n{fence}"

    def test_app_version_mentions_are_neutralised(self, settings, respx_mock):
        settings.MATTERMOST_FEEDBACK_WEBHOOK_URL = "https://mm.example.com/hooks/abc"
        route = respx_mock.post("https://mm.example.com/hooks/abc").respond(200)
        feedback = FeedbackFactory(message="x", app_version="@channel")

        notify_feedback(feedback.pk)  # ty: ignore[unresolved-attribute]

        text = json.loads(route.calls.last.request.content)["text"]
        # app_version is wrapped in inline code, so @channel can't ping the channel.
        assert "app: `@channel`" in text
        assert "app: @channel" not in text

    def test_skips_when_webhook_unset(self, settings, respx_mock):
        settings.MATTERMOST_FEEDBACK_WEBHOOK_URL = None
        feedback = FeedbackFactory()

        notify_feedback(feedback.pk)  # ty: ignore[unresolved-attribute]

        assert not respx_mock.calls

    def test_deleted_feedback_is_a_noop(self, settings, respx_mock):
        settings.MATTERMOST_FEEDBACK_WEBHOOK_URL = "https://mm.example.com/hooks/abc"
        respx_mock.post("https://mm.example.com/hooks/abc").respond(200)

        # No row with this id — must not raise (task isn't retried on DoesNotExist).
        notify_feedback(999_999)

        assert not respx_mock.calls
