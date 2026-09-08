"""API endpoints for file upload (PRD 25.1)."""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import File
from ..serializers import FileSerializer
from ..services.file_service import DuplicateFileError, FileImportError, import_file


@api_view(["POST"])
def upload_file(request):
    """Upload an internal or external transaction CSV.

    Multipart form fields: ``file`` (the CSV), ``source`` (INTERNAL/EXTERNAL).
    Returns the created File object, or a 4xx with a useful error details.
    """
    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "no file provided under the 'file' field"}, status=status.HTTP_400_BAD_REQUEST)

    source = str(request.data.get("source", "")).strip().upper()
    try:
        content = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return Response({"detail": "file is not valid UTF-8 text"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        new_file = import_file(
            filename=upload.name,
            source=source,
            content=content,
            content_bytes=content.encode("utf-8"),
        )
    except DuplicateFileError as exc:
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_409_CONFLICT,
        )
    except FileImportError as exc:
        return Response(
            {"detail": exc.message, "code": exc.code},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return Response(
        {"file": FileSerializer(new_file).data, "detail": "file imported successfully"},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def list_files(request):
    files = File.objects.order_by("-uploaded_at")
    return Response(FileSerializer(files, many=True).data)