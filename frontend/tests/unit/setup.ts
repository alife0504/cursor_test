import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
});

// jsdom 不實作 matchMedia,但 next-themes 等套件會用到
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as typeof window.matchMedia;
}

// jsdom 不實作 PointerEvent;base-ui (checkbox / popover) 需要
if (typeof window !== "undefined" && typeof window.PointerEvent === "undefined") {
  class PointerEventPolyfill extends MouseEvent {
    pointerId: number;
    width: number;
    height: number;
    pressure: number;
    tangentialPressure: number;
    tiltX: number;
    tiltY: number;
    twist: number;
    pointerType: string;
    isPrimary: boolean;
    constructor(type: string, params: PointerEventInit = {}) {
      super(type, params);
      this.pointerId = params.pointerId ?? 0;
      this.width = params.width ?? 1;
      this.height = params.height ?? 1;
      this.pressure = params.pressure ?? 0;
      this.tangentialPressure = params.tangentialPressure ?? 0;
      this.tiltX = params.tiltX ?? 0;
      this.tiltY = params.tiltY ?? 0;
      this.twist = params.twist ?? 0;
      this.pointerType = params.pointerType ?? "mouse";
      this.isPrimary = params.isPrimary ?? true;
    }
    getCoalescedEvents(): PointerEvent[] {
      return [];
    }
    getPredictedEvents(): PointerEvent[] {
      return [];
    }
  }
  // @ts-expect-error 手動 polyfill
  window.PointerEvent = PointerEventPolyfill;
  // @ts-expect-error 手動 polyfill
  globalThis.PointerEvent = PointerEventPolyfill;
}

// jsdom 也沒 hasPointerCapture / releasePointerCapture / scrollIntoView
if (typeof Element !== "undefined") {
  const proto = Element.prototype as unknown as Record<string, unknown>;
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false;
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => undefined;
  if (!proto.setPointerCapture) proto.setPointerCapture = () => undefined;
  if (!proto.scrollIntoView) proto.scrollIntoView = () => undefined;
}

// ResizeObserver — @xyflow / shadcn select 需要
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverPolyfill {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverPolyfill }).ResizeObserver =
    ResizeObserverPolyfill;
}
