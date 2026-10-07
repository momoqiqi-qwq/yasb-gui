"""Short, interruptible WinUI feedback without delaying application actions."""

import ctypes
import weakref
from ctypes import wintypes

from core.logger import warning
from core.preferences import get_preferences
from winrt.windows.foundation import Point
from winui3.microsoft.ui.xaml.controls import Button
from winui3.microsoft.ui.xaml.markup import XamlReader
from winui3.microsoft.ui.xaml.media import MatrixTransform, ScaleTransform, TranslateTransform
from winui3.microsoft.ui.xaml.media.animation import Storyboard

_active = weakref.WeakSet()


def system_animations_enabled():
    enabled = wintypes.BOOL()
    api = ctypes.windll.user32.SystemParametersInfoW
    api.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT]
    api.restype = wintypes.BOOL
    return bool(api(0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)


def animations_enabled():
    return bool(get_preferences().get("ui_animations", True)) and system_animations_enabled()


def _has_identity_transform(control):
    transform = control.render_transform
    if transform is None:
        return True
    try:
        matrix = transform.as_(MatrixTransform).matrix
        return (matrix.m11, matrix.m12, matrix.m21, matrix.m22, matrix.offset_x, matrix.offset_y) == (1, 0, 0, 1, 0, 0)
    except TypeError, OSError:
        return False


def _storyboard(targets, milliseconds, back=False):
    easing = '<BackEase EasingMode="EaseOut" Amplitude="0.3"/>' if back else '<QuadraticEase EasingMode="EaseOut"/>'
    children = "".join(
        f'<DoubleAnimation Storyboard.TargetProperty="{prop}" From="{start}" To="{end}" '
        f'Duration="0:0:{milliseconds / 1000:.3f}"><DoubleAnimation.EasingFunction>{easing}'
        "</DoubleAnimation.EasingFunction></DoubleAnimation>"
        for _, prop, start, end in targets
    )
    result = XamlReader.load(
        '<Storyboard xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation">' + children + "</Storyboard>"
    ).as_(Storyboard)
    for index, (target, _, _, _) in enumerate(targets):
        Storyboard.set_target(result.children.get_at(index), target)
    return result


class _ButtonMotion:
    def __init__(self, control, card=False):
        self.control = control
        self.card = card
        self.storyboard = None
        self.original_transform = control.render_transform
        self.original_origin = control.render_transform_origin
        self.transform = XamlReader.load(
            '<ScaleTransform xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"/>'
        ).as_(ScaleTransform)
        control.render_transform = self.transform
        control.render_transform_origin = Point(0.5, 0.5)
        self.callbacks = []
        try:
            for prop, duration in (
                (Button.is_pressed_property, 80),
                (Button.is_pointer_over_property, 200),
                (Button.is_enabled_property, 80),
            ):
                token = control.register_property_changed_callback(
                    prop, lambda sender, dp, duration=duration: self.update(duration)
                )
                self.callbacks.append((prop, token))
            self.unloaded = control.add_unloaded(self.detach)
        except Exception:
            for prop, token in self.callbacks:
                control.unregister_property_changed_callback(prop, token)
            control.render_transform = self.original_transform
            control.render_transform_origin = self.original_origin
            raise
        _active.add(self)

    def update(self, duration=80):
        control = self.control
        target = 1.0
        if control.is_enabled:
            if control.is_pressed:
                target = 0.97
            elif self.card and control.is_pointer_over:
                # Each card has 4 DIP of inset. Limit growth to 3 DIP per side,
                # including on wide windows, so icons and edges stay unclipped.
                target = 1 + min(0.008, 6 / max(control.actual_width, 1))
        self.animate(target, duration)

    def animate(self, target, duration):
        # Sample the currently displayed value before cancelling the old clock.
        current = self.transform.scale_x
        if self.storyboard:
            self.storyboard.stop()
            self.storyboard = None
        if not self.control.is_enabled or not animations_enabled():
            self.transform.scale_x = self.transform.scale_y = 1.0
            return
        self.transform.scale_x = self.transform.scale_y = current
        if abs(current - target) < 0.0001:
            return
        self.storyboard = _storyboard(
            [(self.transform, "ScaleX", current, target), (self.transform, "ScaleY", current, target)],
            duration,
            back=self.card and target > 1,
        )
        self.storyboard.begin()

    def reset(self):
        if self.storyboard:
            self.storyboard.stop()
            self.storyboard = None
        self.transform.scale_x = self.transform.scale_y = 1.0

    def detach(self, sender, args):
        self.reset()
        for prop, token in self.callbacks:
            self.control.unregister_property_changed_callback(prop, token)
        self.control.remove_unloaded(self.unloaded)
        self.control.render_transform = self.original_transform
        self.control.render_transform_origin = self.original_origin
        _active.discard(self)
        self.control = None


def _loaded(sender, card):
    try:
        control = sender.as_(Button)
        # Respect transforms explicitly owned by another feature.
        if _has_identity_transform(control):
            _ButtonMotion(control, card)
    except Exception as exc:
        warning(f"Button motion unavailable: {exc}")


def _button_loaded(sender, args):
    _loaded(sender, False)


def _card_loaded(sender, args):
    _loaded(sender, True)


def instrument_button(button, *, card=False):
    # A static Loaded callback retains no reference to the button. Per-load
    # callbacks are removed on Unloaded, including on cached page navigation.
    button.add_loaded(_card_loaded if card else _button_loaded)
    return button


class PageMotion:
    def __init__(self, host):
        self.host = host
        self.storyboard = None
        self.transform = None
        if _has_identity_transform(host):
            self.transform = XamlReader.load(
                '<TranslateTransform xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"/>'
            ).as_(TranslateTransform)
            host.render_transform = self.transform
        _active.add(self)

    def reset(self):
        if self.storyboard:
            self.storyboard.stop()
            self.storyboard = None
        self.host.opacity = 1.0
        if self.transform:
            self.transform.y = 0.0

    def play(self):
        self.reset()
        if not self.transform or not animations_enabled():
            return
        self.storyboard = _storyboard([(self.host, "Opacity", 0, 1), (self.transform, "Y", 12, 0)], 240)
        self.storyboard.begin()


def reset_animations():
    for state in list(_active):
        state.reset()
