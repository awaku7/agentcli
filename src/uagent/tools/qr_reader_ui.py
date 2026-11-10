"""Standalone Tkinter QR reader window; camera access and decoding stay local."""

from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any


def _translate_ui(
    strings: dict[str, str], key: str, default: str, **kwargs: Any
) -> str:
    template = strings.get(key, default)
    if not kwargs:
        return template
    try:
        return template % kwargs
    except (KeyError, TypeError, ValueError):
        try:
            return template.format(**kwargs)
        except (KeyError, TypeError, ValueError):
            return default % kwargs


class QRReaderWindow:
    def __init__(
        self,
        root: tk.Tk,
        cv2: Any,
        image_module: Any,
        image_tk: Any,
        strings: dict[str, str] | None = None,
    ) -> None:
        self.root = root
        self.strings = strings or {}
        self.cv2 = cv2
        self.image_module = image_module
        self.image_tk = image_tk
        self.detector = cv2.QRCodeDetector()
        self.capture: Any = None
        self._camera_after_id: str | None = None
        self.preview_image: Any = None
        self.last_data = ""
        self._last_seen: dict[str, float] = {}

        root.title(self._t("ui.title", "UAG QR Reader"))
        root.geometry("980x760")
        root.minsize(760, 560)
        root.protocol("WM_DELETE_WINDOW", self.close)

        toolbar = ttk.Frame(root, padding=8)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text=self._t("ui.camera", "Camera:")).pack(side="left")
        self.camera_index = tk.IntVar(value=0)
        ttk.Spinbox(
            toolbar, from_=0, to=16, width=4, textvariable=self.camera_index
        ).pack(side="left", padx=(4, 10))
        ttk.Button(
            toolbar,
            text=self._t("ui.start_camera", "Start camera"),
            command=self.start_camera,
        ).pack(side="left", padx=3)
        ttk.Button(
            toolbar,
            text=self._t("ui.stop_camera", "Stop camera"),
            command=self.stop_camera,
        ).pack(side="left", padx=3)
        ttk.Button(
            toolbar,
            text=self._t("ui.open_image", "Open image..."),
            command=self.open_image,
        ).pack(side="left", padx=(12, 3))
        ttk.Button(
            toolbar,
            text=self._t("ui.copy_latest", "Copy latest"),
            command=self.copy_latest,
        ).pack(side="left", padx=3)
        ttk.Button(
            toolbar,
            text=self._t("ui.send_to_uag", "Send to UAG"),
            command=self.send_to_uag,
        ).pack(side="left", padx=3)
        ttk.Button(
            toolbar, text=self._t("ui.clear", "Clear"), command=self.clear_results
        ).pack(side="left", padx=3)

        self.status = tk.StringVar(
            value=self._t(
                "ui.initial_status",
                "Choose an image or start the camera. QR data stays on this device.",
            )
        )
        ttk.Label(root, textvariable=self.status, padding=(10, 2)).pack(fill="x")

        body = ttk.Frame(root, padding=(8, 4, 8, 8))
        body.pack(fill="both", expand=True)
        self.preview = ttk.Label(
            body,
            text=self._t("ui.preview_placeholder", "Camera preview / selected image"),
            anchor="center",
            relief="sunken",
        )
        self.preview.pack(side="left", fill="both", expand=True, padx=(0, 8))

        output_frame = ttk.Frame(body, width=300)
        output_frame.pack(side="right", fill="y")
        output_frame.pack_propagate(False)
        ttk.Label(
            output_frame,
            text=self._t("ui.decoded_content", "Decoded QR content"),
        ).pack(anchor="w")
        self.output = tk.Text(output_frame, wrap="word", height=20, width=35)
        self.output.pack(side="left", fill="both", expand=True, pady=(4, 0))
        scrollbar = ttk.Scrollbar(output_frame, command=self.output.yview)
        scrollbar.pack(side="right", fill="y", pady=(4, 0))
        self.output.configure(yscrollcommand=scrollbar.set)

    def _t(self, key: str, default: str, **kwargs: Any) -> str:
        return _translate_ui(self.strings, key, default, **kwargs)

    def _decode(self, frame: Any) -> tuple[list[str], Any]:
        """Decode one or more QR codes, with a single-code fallback."""
        try:
            multi_result = self.detector.detectAndDecodeMulti(frame)
            if multi_result and multi_result[0]:
                values = [value for value in multi_result[1] if value]
                return values, multi_result[2]
        except Exception:
            pass

        value, points, _straight = self.detector.detectAndDecode(frame)
        return ([value] if value else []), points

    def _record_results(self, values: list[str]) -> None:
        now = time.monotonic()
        for value in values:
            if not value:
                continue
            self.last_data = value
            if now - self._last_seen.get(value, 0.0) < 2.0:
                continue
            self._last_seen[value] = now
            stamp = time.strftime("%H:%M:%S")
            self.output.insert("end", f"[{stamp}]\n{value}\n\n")
            self.output.see("end")
            self.last_data = value
            self.status.set(
                self._t(
                    "ui.decoded_status",
                    "QR code decoded. Use 'Copy latest' to copy its contents.",
                )
            )

    def _show_frame(self, frame: Any) -> None:
        height, width = frame.shape[:2]
        scale = min(1.0, 720 / max(width, 1), 620 / max(height, 1))
        if scale < 1.0:
            frame = self.cv2.resize(
                frame,
                (max(1, int(width * scale)), max(1, int(height * scale))),
                interpolation=self.cv2.INTER_AREA,
            )
        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        image = self.image_module.fromarray(rgb)
        self.preview_image = self.image_tk.PhotoImage(image=image)
        self.preview.configure(image=self.preview_image, text="")

    def start_camera(self) -> None:
        self.stop_camera()
        try:
            index = int(self.camera_index.get())
        except (TypeError, ValueError):
            self.status.set(
                self._t("ui.invalid_camera_index", "Camera index must be a number.")
            )
            return

        capture = self.cv2.VideoCapture(index)
        if not capture.isOpened():
            capture.release()
            self.status.set(
                self._t(
                    "ui.camera_open_error",
                    "Could not open camera %(index)s. Try another index or open an image.",
                    index=index,
                )
            )
            return
        self.capture = capture
        self.status.set(
            self._t(
                "ui.camera_scanning",
                "Scanning with camera %(index)s. Press 'Stop camera' to stop.",
                index=index,
            )
        )
        self._camera_tick()

    def _camera_tick(self) -> None:
        self._camera_after_id = None
        if self.capture is None:
            return
        ok, frame = self.capture.read()
        if ok:
            values, points = self._decode(frame)
            if points is not None:
                try:
                    for polygon in points:
                        self.cv2.polylines(
                            frame,
                            [self.cv2.convexHull(polygon).astype("int32")],
                            True,
                            (0, 220, 0),
                            2,
                        )
                except Exception:
                    pass
            self._record_results(values)
            self._show_frame(frame)
        if self.capture is not None:
            self._camera_after_id = self.root.after(30, self._camera_tick)

    def stop_camera(self) -> None:
        if self._camera_after_id is not None:
            try:
                self.root.after_cancel(self._camera_after_id)
            except tk.TclError:
                pass
            self._camera_after_id = None
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.status.set(self._t("ui.camera_stopped", "Camera stopped."))

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self._t(
                "ui.choose_image_title", "Choose an image containing a QR code"
            ),
            filetypes=[
                (
                    self._t("ui.image_files", "Image files"),
                    "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp",
                ),
                (self._t("ui.all_files", "All files"), "*.*"),
            ],
        )
        if not path:
            return
        self.stop_camera()
        frame = self.cv2.imread(path)
        if frame is None:
            self.status.set(
                self._t("ui.image_open_error", "Could not open the selected image.")
            )
            return
        values, points = self._decode(frame)
        if points is not None:
            try:
                for polygon in points:
                    self.cv2.polylines(
                        frame,
                        [self.cv2.convexHull(polygon).astype("int32")],
                        True,
                        (0, 220, 0),
                        2,
                    )
            except Exception:
                pass
        self._show_frame(frame)
        if values:
            self._record_results(values)
        else:
            self.status.set(
                self._t("ui.no_qr_found", "No QR code was found in that image.")
            )

    def copy_latest(self) -> None:
        if not self.last_data:
            self.status.set(
                self._t("ui.copy_empty", "There is no decoded content to copy yet.")
            )
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_data)
        self.root.update_idletasks()
        self.status.set(
            self._t("ui.copied", "Latest QR content copied to the clipboard.")
        )

    def send_to_uag(self) -> None:
        if not self.last_data:
            self.status.set(
                self._t("ui.send_empty", "There is no decoded content to send yet.")
            )
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.last_data)
            self.root.update_idletasks()
            sys.stdout.write(
                json.dumps({"text": self.last_data}, ensure_ascii=True) + "\n"
            )
            sys.stdout.flush()
        except Exception as exc:
            self.status.set(
                self._t(
                    "ui.send_error",
                    "Could not send QR content to UAG: %(error_type)s",
                    error_type=type(exc).__name__,
                )
            )
            return
        self.close()

    def clear_results(self) -> None:
        self.output.delete("1.0", "end")
        self.last_data = ""
        self._last_seen.clear()
        self.status.set(self._t("ui.results_cleared", "Results cleared."))

    def close(self) -> None:
        self.stop_camera()
        self.root.destroy()


def main() -> int:
    try:
        loaded = json.loads(os.environ.get("UAGENT_QR_READER_STRINGS", "{}"))
        strings = (
            {key: value for key, value in loaded.items() if isinstance(value, str)}
            if isinstance(loaded, dict)
            else {}
        )
    except (json.JSONDecodeError, TypeError):
        strings = {}

    try:
        import cv2
        from PIL import Image, ImageTk
    except ImportError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            _translate_ui(strings, "ui.unavailable_title", "QR Reader unavailable"),
            _translate_ui(
                strings,
                "ui.missing_dependency",
                "Required image-scanning package is missing: %(error)s",
                error=exc,
            ),
            parent=root,
        )
        root.destroy()
        return 1

    root = tk.Tk()
    QRReaderWindow(root, cv2, Image, ImageTk, strings=strings)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
