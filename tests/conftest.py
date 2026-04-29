from pathlib import Path
import pytest


# root_path is project's root path = parent of ~/tests.
@pytest.fixture
def root_path(request):
    return request.config.rootpath


# Prefix to save images under ~/tests/assets/
@pytest.fixture
def prefix(root_path):
    full_path = Path(root_path) / "tests" / "assets" / "test"
    return str(full_path.relative_to(Path.cwd()))


# Two json files to test
@pytest.fixture
def camera_dict_name(root_path):
    full_path = Path(root_path) / "tests" / "assets" / "camera_dict.json"
    return str(full_path.relative_to(Path.cwd()))


@pytest.fixture
def camera_gst_name(root_path):
    full_path = Path(root_path) / "tests" / "assets" / "camera_gst_dict.json"
    return str(full_path.relative_to(Path.cwd()))
