MACHINE_TEST_TYPES_BY_MODE = {
    "roasting": {
        "MoistureDensity",
        "RoastColor",
        "Colour",
        "EndTemperature",
    },
    "packaging": {
        "GasAnalysis",
        "PackageWeight",
        "BUB",
        "PackagingColor",
    },
}


MACHINE_TEST_TYPE_LABELS = {
    "MoistureDensity": "Moisture/density result",
    "RoastColor": "Roast color result",
    "Colour": "Color result",
    "EndTemperature": "End temperature result",
    "GasAnalysis": "CheckMate 3/O2 result",
    "PackageWeight": "Package weight result",
    "BUB": "BUB result",
    "PackagingColor": "Packaging color result",
}


MODE_LABELS = {
    "roasting": "Roasting Tests",
    "packaging": "Packaging Tests",
}


def is_machine_test_type(
    test_type: str,
) -> bool:
    for allowed_test_types in MACHINE_TEST_TYPES_BY_MODE.values():
        if test_type in allowed_test_types:
            return True

    return False


def is_machine_test_allowed_for_mode(
    test_type: str,
    mode: str,
) -> bool:
    if not is_machine_test_type(
        test_type
    ):
        return True

    allowed_test_types = MACHINE_TEST_TYPES_BY_MODE.get(
        mode,
        set(),
    )

    return test_type in allowed_test_types


def get_expected_mode_for_machine_test(
    test_type: str,
) -> str | None:
    for mode, allowed_test_types in MACHINE_TEST_TYPES_BY_MODE.items():
        if test_type in allowed_test_types:
            return mode

    return None


def get_machine_test_label(
    test_type: str,
) -> str:
    return MACHINE_TEST_TYPE_LABELS.get(
        test_type,
        test_type or "Unknown machine input",
    )


def get_mode_label(
    mode: str,
) -> str:
    return MODE_LABELS.get(
        mode,
        mode or "No Mode Selected",
    )


def build_wrong_machine_mode_message(
    com_port: str,
    test_type: str,
    current_mode: str,
) -> str:
    test_label = get_machine_test_label(
        test_type
    )

    current_mode_label = get_mode_label(
        current_mode
    )

    expected_mode = get_expected_mode_for_machine_test(
        test_type
    )

    if expected_mode is None:
        return (
            f"{com_port}: NOT SAVED: "
            f"{test_label} is not supported in {current_mode_label}."
        )

    expected_mode_label = get_mode_label(
        expected_mode
    )

    return (
        f"{com_port}: NOT SAVED: "
        f"{test_label} received while {current_mode_label} is selected. "
        f"Switch to {expected_mode_label}."
    )