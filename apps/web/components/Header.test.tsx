import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Header } from "./Header";

describe("Header", () => {
  it("renders without crashing", () => {
    const { container } = render(<Header />);
    expect(container.firstChild).toBeTruthy();
  });
});
