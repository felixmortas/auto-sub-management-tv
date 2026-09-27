def json_exact_match(actual, expected):
    """Compare JSON values while ignoring case, dictionary ordering and list ordering."""

    if type(actual) is not type(expected):
        return False

    if isinstance(actual, dict):
        # Normalise les clés sans tenir compte de la casse.
        actual_normalized = {key.lower(): value for key, value in actual.items()}
        expected_normalized = {key.lower(): value for key, value in expected.items()}

        if actual_normalized.keys() != expected_normalized.keys():
            return False

        return all(
            json_exact_match(
                actual_normalized[key],
                expected_normalized[key],
            )
            for key in actual_normalized
        )

    if isinstance(actual, list):
        if len(actual) != len(expected):
            return False

        unmatched = list(expected)

        for actual_item in actual:
            for index, expected_item in enumerate(unmatched):
                if json_exact_match(actual_item, expected_item):
                    unmatched.pop(index)
                    break
            else:
                return False

        return True

    if isinstance(actual, str):
        return actual.casefold() == expected.casefold()

    return actual == expected


def perform_eval(run, example):
    """Check whether the structured output exactly matches the reference."""

    return {
        "exact_match": json_exact_match(
            run["outputs"],
            example["outputs"],
        )
    }