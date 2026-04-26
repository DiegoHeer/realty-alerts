import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HowItWorks } from "./HowItWorks";

describe("HowItWorks", () => {
  it("renders without crashing", () => {
    const { container } = render(<HowItWorks />);
    expect(container.firstChild).toBeTruthy();
  });
});
