from dataclasses import dataclass


@dataclass(frozen=True)
class StrokeSegment:
    video: str
    label: str
    start_frame: int
    end_frame: int

    @property
    def duration_frames(self) -> int:
        return max(0, self.end_frame - self.start_frame + 1)
