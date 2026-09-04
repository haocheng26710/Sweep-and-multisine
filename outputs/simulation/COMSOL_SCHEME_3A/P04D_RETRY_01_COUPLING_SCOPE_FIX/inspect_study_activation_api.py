"""Read-only reflection of COMSOL 6.4 study-step activation methods."""

from pathlib import Path

import mph


AUTHORITY = Path(r"D:\Bristol course\dissertation\program work\outputs\simulation\COMSOL_SCHEME_3A\P04B_NOMINAL_CROSS_MODULE_VALIDATION\P04BN_HR03_PRODUCTION.mph")


def main() -> None:
    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    model = client.load(AUTHORITY)
    try:
        step = model.java.study("std_freq").feature("step1")
        methods = sorted(
            {
                str(method)
                for method in step.getClass().getMethods()
                if any(token in str(method).lower() for token in ("activ", "solvefor", "physics"))
            }
        )
        for method in methods:
            print(method)
        print("PROPERTIES", [str(value) for value in step.properties()])
        for prop in step.properties():
            try:
                print("PROPERTY", prop, str(step.getString(str(prop))))
            except Exception:
                pass
        solution = model.java.sol("sol1")
        print("SOLUTION_METHODS")
        for method in sorted(
            {
                str(method)
                for method in solution.getClass().getMethods()
                if any(token in str(method).lower() for token in ("size", "dof", "solutioninfo"))
            }
        ):
            print(method)
        info = solution.getSolutioninfo()
        print("SOLUTION_INFO_METHODS")
        for method in sorted(
            {
                str(method)
                for method in info.getClass().getMethods()
                if any(token in str(method).lower() for token in ("size", "dof", "field", "name", "map"))
            }
        ):
            print(method)
    finally:
        client.remove(model)
        client.clear()


if __name__ == "__main__":
    main()
