import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Hero } from "./Hero";

describe("Hero", () => {
  it("renders without crashing", () => {
    const { container } = render(<Hero />);
    expect(container.firstChild).toBeTruthy();
  });
});
