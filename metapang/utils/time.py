import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class TimeStep:
    """A single timing step or lap with formatting helpers."""

    name: str
    absolute_time: float  # Time since timer start
    step_duration: float  # Duration of this step only
    timestamp: int  # When this step was recorded (nanoseconds)
    format_str: str = "%Hh%Mm%Ss"  # Default format for displaying time

    def format_absolute(
        self, format_type: str = "auto", precision: int = 9, custom_format: str = None
    ) -> str:
        """Format the absolute time since timer start."""
        if custom_format:
            return TimeFormatter.format_custom(
                self.absolute_time, custom_format, precision
            )
        return TimeFormatter.format_time(self.absolute_time, format_type, precision)

    def format_duration(
        self, format_type: str = "auto", precision: int = 9, custom_format: str = None
    ) -> str:
        """Format this step's own duration."""
        if custom_format:
            return TimeFormatter.format_custom(
                self.step_duration, custom_format, precision
            )
        return TimeFormatter.format_time(self.step_duration, format_type, precision)

    def format(self) -> str:
        """Format the absolute time using the step's format string."""
        return TimeFormatter.format_custom(
            self.absolute_time, self.format_str, precision=9
        )

    def __str__(self) -> str:
        return (
            f"{self.name}: {self.format_duration()} (total: {self.format_absolute()})"
        )

    def __repr__(self) -> str:
        return f"TimeStep(name='{self.name}', duration={self.step_duration:.9f}s, absolute={self.absolute_time:.9f}s)"


class TimeFormatter:
    """Static helpers to format durations (in seconds) as readable strings."""

    @staticmethod
    def format_time(
        seconds: float, format_type: str = "auto", precision: int = 9
    ) -> str:
        """Format a duration in seconds, auto-selecting units by default."""
        if format_type == "seconds":
            return f"{seconds:.{precision}f}s"
        elif format_type == "milliseconds":
            return f"{seconds * 1000:.{max(0, precision - 3)}f}ms"
        elif format_type == "microseconds":
            return f"{seconds * 1_000_000:.{max(0, precision - 6)}f}μs"
        elif format_type == "nanoseconds":
            return f"{seconds * 1_000_000_000:.0f}ns"
        elif format_type == "minutes":
            minutes = seconds / 60
            return f"{minutes:.{precision}f}m"
        elif format_type == "hours":
            hours = seconds / 3600
            return f"{hours:.{precision}f}h"
        elif format_type == "precise":
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            if hours > 0:
                return f"{hours}h {minutes}m {secs:.{precision}f}s"
            elif minutes > 0:
                return f"{minutes}m {secs:.{precision}f}s"
            else:
                return f"{secs:.{precision}f}s"
        else:
            if seconds < 1e-6:
                return f"{seconds * 1_000_000_000:.0f}ns"
            elif seconds < 1e-3:
                return f"{seconds * 1_000_000:.{max(0, precision - 6)}f}μs"
            elif seconds < 1:
                return f"{seconds * 1000:.{max(0, precision - 3)}f}ms"
            elif seconds < 60:
                return f"{seconds:.{precision}f}s"
            elif seconds < 3600:
                minutes = seconds / 60
                return f"{minutes:.2f}m"
            else:
                hours = seconds / 3600
                return f"{hours:.2f}h"

    @staticmethod
    def format_multiple(
        times: list[float], format_type: str = "auto", precision: int = 9
    ) -> list[str]:
        """Format multiple durations at once."""
        return [TimeFormatter.format_time(t, format_type, precision) for t in times]

    @staticmethod
    def format_custom(seconds: float, format_string: str, precision: int = 9) -> str:
        """Format a duration with a template (%H, %M, %S, %s, %f, %ms, %us, %ns, %%)."""
        total_seconds = seconds
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs_int = int(seconds % 60)
        fractional = seconds - int(seconds)

        total_ms = seconds * 1000
        total_us = seconds * 1_000_000
        total_ns = int(seconds * 1_000_000_000)

        replacements = {
            "%H": str(hours),
            "%M": str(minutes),
            "%S": str(secs_int),
            "%s": f"{total_seconds:.{precision}f}",
            "%f": f"{fractional:.{precision}f}"[2:],
            "%ms": f"{total_ms:.{max(0, precision - 3)}f}",
            "%us": f"{total_us:.{max(0, precision - 6)}f}",
            "%ns": str(total_ns),
            "%%": "%",
        }

        result = format_string
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result


class StepCollection:
    """Ordered collection of timing steps with lookup and formatting helpers."""

    def __init__(self, format: str = "%Hh%Mm%Ss"):
        self._steps: list[TimeStep] = []
        self._format = format

    def add_step(
        self, name: str, absolute_time: float, step_duration: float, timestamp: int
    ) -> TimeStep:
        """Create, append, and return a new step."""
        step = TimeStep(name, absolute_time, step_duration, timestamp, self._format)
        self._steps.append(step)
        return step

    def get_step(self, identifier: str | int) -> TimeStep | None:
        """Get a step by name or index, or None if absent."""
        if isinstance(identifier, str):
            for step in self._steps:
                if step.name == identifier:
                    return step
            return None
        elif isinstance(identifier, int):
            try:
                return self._steps[identifier]
            except IndexError:
                return None
        return None

    def get_last_step(self) -> TimeStep | None:
        """Return the most recent step, or None if empty."""
        return self._steps[-1] if self._steps else None

    def get_all_steps(self) -> list[TimeStep]:
        """Return a copy of all steps."""
        return self._steps.copy()

    def get_step_names(self) -> list[str]:
        """Return the names of all steps."""
        return [step.name for step in self._steps]

    def get_durations(self) -> list[float]:
        """Return each step's own duration."""
        return [step.step_duration for step in self._steps]

    def get_absolute_times(self) -> list[float]:
        """Return each step's time since timer start."""
        return [step.absolute_time for step in self._steps]

    def format_all_durations(
        self, format_type: str = "auto", precision: int = 9
    ) -> list[str]:
        """Format every step's own duration."""
        return [step.format_duration(format_type, precision) for step in self._steps]

    def format_all_absolute(
        self, format_type: str = "auto", precision: int = 9
    ) -> list[str]:
        """Format every step's absolute time."""
        return [step.format_absolute(format_type, precision) for step in self._steps]

    def clear(self):
        """Remove all steps."""
        self._steps.clear()

    def __len__(self) -> int:
        return len(self._steps)

    def __iter__(self):
        return iter(self._steps)

    def __getitem__(self, key: str | int) -> TimeStep | None:
        return self.get_step(key)


class Timer:
    """Stopwatch with pause/resume, lap steps, and flexible formatting."""

    def __init__(
        self,
        name: str = "Timer",
        auto_start: bool = False,
        format: str = "%Hh%Mm%Ss",
        precision: int = 9,
    ):
        self.name = name
        self.precision = precision
        self._start_time: int | None = None
        self._end_time: int | None = None
        self._paused_time: int = 0
        self._pause_start: int | None = None
        self._is_running: bool = False
        self._is_paused: bool = False
        self.steps = StepCollection()
        self.custom_format: str = format

        if auto_start:
            self.start()

    def start(self) -> "Timer":
        """Start the timer, or resume it if paused."""
        current_time = time.perf_counter_ns()

        if self._is_running and not self._is_paused:
            return self
        elif self._is_paused:
            if self._pause_start is not None:
                self._paused_time += current_time - self._pause_start
                self._pause_start = None
            self._is_paused = False
        else:
            self._start_time = current_time
            self._paused_time = 0
            self.steps.clear()

        self._is_running = True
        self._end_time = None
        return self

    def stop(self) -> float:
        """Stop the timer and return the elapsed seconds."""
        if not self._is_running:
            return 0.0

        if self._is_paused and self._pause_start is not None:
            self._paused_time += time.perf_counter_ns() - self._pause_start
            self._pause_start = None

        self._end_time = time.perf_counter_ns()
        self._is_running = False
        self._is_paused = False
        return self.elapsed

    def pause(self) -> "Timer":
        """Pause the timer."""
        if self._is_running and not self._is_paused:
            self._pause_start = time.perf_counter_ns()
            self._is_paused = True
        return self

    def resume(self) -> "Timer":
        """Resume a paused timer."""
        return self.start()

    def reset(self) -> "Timer":
        """Reset the timer to its initial state."""
        self._start_time = None
        self._end_time = None
        self._paused_time = 0
        self._pause_start = None
        self._is_running = False
        self._is_paused = False
        self.steps.clear()
        return self

    def step(self, name: str = None) -> TimeStep:
        """Record a lap step and return it."""
        if not self._is_running:
            return TimeStep(name or "Invalid", 0.0, 0.0, time.perf_counter_ns())

        current_time = time.perf_counter_ns()
        current_elapsed = self._calculate_elapsed(current_time)

        last_step = self.steps.get_last_step()
        if last_step:
            step_duration = current_elapsed - last_step.absolute_time
        else:
            step_duration = current_elapsed

        step_name = name or f"Step {len(self.steps) + 1}"
        return self.steps.add_step(
            step_name, current_elapsed, step_duration, current_time
        )

    def get_step(self, identifier: str | int) -> TimeStep | None:
        """Get a recorded step by name or index."""
        return self.steps.get_step(identifier)

    def get_last_step(self) -> TimeStep | None:
        """Return the most recent recorded step."""
        return self.steps.get_last_step()

    def _calculate_elapsed(self, end_time: int | None = None) -> float:
        """Compute elapsed seconds up to end_time, excluding paused time."""
        if self._start_time is None:
            return 0.0

        if end_time is None:
            end_time = time.perf_counter_ns()

        total_time_ns = end_time - self._start_time

        paused_time_ns = self._paused_time
        if self._is_paused and self._pause_start is not None:
            paused_time_ns += end_time - self._pause_start

        elapsed_ns = max(0, total_time_ns - paused_time_ns)
        return elapsed_ns / 1_000_000_000.0

    @property
    def elapsed(self) -> float:
        """Elapsed seconds, excluding paused intervals."""
        if self._start_time is None:
            return 0.0

        if self._end_time is not None:
            return self._calculate_elapsed(self._end_time)
        else:
            return self._calculate_elapsed()

    @property
    def is_running(self) -> bool:
        """Whether the timer is currently running."""
        return self._is_running

    @property
    def is_paused(self) -> bool:
        """Whether the timer is currently paused."""
        return self._is_paused

    def format_time(
        self,
        seconds: float = None,
        format_type: str = "auto",
        custom_format: str = None,
    ) -> str:
        """Format the given seconds, or the elapsed time if omitted."""
        if seconds is None:
            seconds = self.elapsed
        if custom_format:
            return TimeFormatter.format_custom(seconds, custom_format, self.precision)
        return TimeFormatter.format_time(seconds, format_type, self.precision)

    def format_elapsed(
        self, format_type: str = "auto", custom_format: str = None
    ) -> str:
        """Format the elapsed time."""
        return self.format_time(self.elapsed, format_type, custom_format)

    def format(self, format: str | None = None) -> str:
        """Format the elapsed time using the custom format string."""
        return self.format_elapsed(custom_format=format or self.custom_format)


@contextmanager
def timer(name: str = "Block"):
    """Context manager that times the enclosed block."""
    t = Timer(name)
    t.start()
    try:
        yield t
    finally:
        t.stop()
