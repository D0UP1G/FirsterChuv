"""Server-owned compiler definitions; bundle data cannot supply commands/images."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompilerSpec:
    language_id: str
    display_name: str
    image: str
    source_filename: str
    compile_argv: tuple[str, ...]
    default_template: str
    verified: bool


COMPILERS: dict[str, CompilerSpec] = {
    "cpp20": CompilerSpec(
        language_id="cpp20",
        display_name="C++20",
        image="firsterchuv/sandbox-cpp:0.1.0",
        source_filename="main.cpp",
        compile_argv=(
            "g++",
            "-std=c++20",
            "-O2",
            "-pipe",
            "-fno-diagnostics-color",
            "-fmax-errors=20",
            "/work/main.cpp",
            "-o",
            "/work/program",
        ),
        default_template="#include <iostream>\nint main() {\n    return 0;\n}\n",
        # The code/image are defined by the sandbox harness; mark usable only after runtime proof.
        verified=False,
    ),
}


def get_compiler(language_id: str) -> CompilerSpec:
    try:
        return COMPILERS[language_id]
    except KeyError as error:
        raise ValueError(f"unsupported compiler language: {language_id}") from error
