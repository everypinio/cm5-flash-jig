from dataclasses import dataclass


class FlashError(RuntimeError):
    pass


@dataclass(frozen=True)
class BlockDevice:
    path: str
    name: str
    kind: str
    removable: bool
    size: str
    model: str | None
    serial: str | None
    mountpoints: tuple[str, ...]
    children: tuple["BlockDevice", ...]

    @property
    def has_mounts(self) -> bool:
        """Returns True if this device or any of its partitions are mounted."""
        if self.mountpoints:
            return True
        return any(child.has_mounts for child in self.children)

    @property
    def child_mountpoints(self) -> tuple[str, ...]:
        """Returns all mountpoints of this device and its children."""
        mounts = list(self.mountpoints)
        for child in self.children:
            mounts.extend(child.child_mountpoints)
        return tuple(mounts)
