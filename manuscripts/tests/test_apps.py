from manuscripts.apps import ManuscriptsConfig


def test_manuscripts_config_name():
    assert ManuscriptsConfig.name == "manuscripts"
