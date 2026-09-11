def json_exact_match(actual, expected):
    """Compare JSON values while ignoring dictionary and list ordering."""

    if type(actual) is not type(expected):
        return False

    if isinstance(actual, dict):
        if set(actual.keys()) != set(expected.keys()):
            return False

        return all(
            json_exact_match(actual[key], expected[key])
            for key in actual
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

    return actual == expected


def perform_eval(run, example):
    """Check whether the structured output exactly matches the reference."""

    return {
        "exact_match": json_exact_match(
            run["outputs"],
            example["outputs"]
        )
    }