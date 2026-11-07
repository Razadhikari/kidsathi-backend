from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.children.models import Child
from apps.core.permissions import SCHOOL_ADMIN, STAFF_ROLES, TEACHER, school_roles
from apps.core.views import SchoolScopedViewSet
from apps.messaging.models import Notice, NoticeRead, Thread
from apps.messaging.serializers import (
    MessageSerializer,
    NoticeSerializer,
    ParentNoticeSerializer,
    PostMessageSerializer,
    StartThreadSerializer,
    ThreadSerializer,
)
from apps.messaging.services import mark_thread_read, post_message, start_thread, visible_notices


class ThreadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """My conversations (parents and staff). Only participants can see a thread."""

    serializer_class = ThreadSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Thread.objects.none()
        return (
            Thread.objects.filter(participants=self.request.user)
            .select_related("child")
            .prefetch_related("participants", "participant_links")
            .distinct()
        )

    @extend_schema(request=StartThreadSerializer, responses=ThreadSerializer)
    def create(self, request, *args, **kwargs):
        s = StartThreadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        child = (
            Child.objects.filter(pk=s.validated_data["child"], is_active=True)
            .select_related("school", "classroom")
            .first()
        )
        if child is None:
            raise NotFound("Child not found.")
        thread = start_thread(
            starter=request.user, child=child, body=s.validated_data["body"], subject=s.validated_data["subject"]
        )
        return Response(ThreadSerializer(thread, context=self.get_serializer_context()).data, status=201)

    @extend_schema(methods=["POST"], request=PostMessageSerializer, responses=MessageSerializer)
    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        thread = self.get_object()
        ctx = {"request": request}
        if request.method == "POST":
            s = PostMessageSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            msg = post_message(thread=thread, sender=request.user, body=s.validated_data["body"])
            return Response(MessageSerializer(msg, context=ctx).data, status=status.HTTP_201_CREATED)
        mark_thread_read(thread, request.user)
        return Response(MessageSerializer(thread.messages.select_related("sender"), many=True, context=ctx).data)


class NoticeViewSet(SchoolScopedViewSet):
    """Staff: the school's notice board (needs X-School-ID)."""

    queryset = Notice.objects.select_related("classroom", "author")
    serializer_class = NoticeSerializer
    permission_classes = [school_roles(read=STAFF_ROLES, write={SCHOOL_ADMIN, TEACHER})]

    def perform_create(self, serializer):
        serializer.save(school=self.school, author=self.request.user)

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"])
    def reads(self, request, pk=None):
        """Read receipts: who has opened this notice."""
        notice = self.get_object()
        readers = notice.reads.select_related("user")
        return Response(
            {"read_count": readers.count(), "readers": [r.user.full_name or r.user.phone_number for r in readers]}
        )


class MyNoticesView(generics.ListAPIView):
    """Parents: notices from my children's schools and classes."""

    serializer_class = ParentNoticeSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notice.objects.none()
        return visible_notices(self.request.user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = getattr(self.request, "user", None)
        if user is not None and user.is_authenticated:
            ctx["read_ids"] = set(NoticeRead.objects.filter(user=user).values_list("notice_id", flat=True))
        return ctx


class MarkNoticeReadView(APIView):
    """Parents: mark a notice as read."""

    @extend_schema(request=None, responses={204: None})
    def post(self, request, notice_id):
        notice = get_object_or_404(visible_notices(request.user), pk=notice_id)
        NoticeRead.objects.get_or_create(notice=notice, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
