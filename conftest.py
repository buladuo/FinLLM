# conftest.py
import pytest

def pytest_addoption(parser):
    parser.addoption("--model", action="store", default="glm-4",
                     help="Specify the model name to test with.")

@pytest.fixture
def model(request):
    return request.config.getoption("--model")
