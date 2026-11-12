import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { makePass } from "../test-helpers";
import { CredentialsSlide } from "./CredentialsSlide";

describe("CredentialsSlide", () => {
  it.each(["ab  cd", " abcd ", 'a:{b};c\\d"', "x".repeat(128)])(
    "shows exact credentials with visible boundaries: %s",
    (password) => {
      const pass = makePass("wifi", { layout: "credentials", lang: "both" });
      pass.content.wifi_credentials = { ssid: " LAN  {main}:1 ", password };
      // Translated prose must not become the source of credential values.
      pass.content.footer = { hu: "Jelszó: wrong", en: "Password: wrong" };
      render(<CredentialsSlide pass={pass} />);
      const value = document.querySelector('[data-credential-value="password"]');
      expect(value?.textContent).toBe(password);
      expect(document.querySelector('[data-credential-value="ssid"]')?.textContent).toBe(" LAN  {main}:1 ");
      expect(value?.parentElement?.textContent).toBe(`"${password}"`);
      expect(value?.parentElement).toHaveClass("whitespace-pre-wrap");
      expect(document.querySelectorAll("[data-credential-value]")).toHaveLength(2);
    },
  );

  it("shows only the network for open Wi-Fi", () => {
    const pass = makePass("wifi", { layout: "credentials" });
    pass.content.wifi_credentials = { ssid: "Open LAN", password: null };
    render(<CredentialsSlide pass={pass} />);
    expect(document.querySelector('[data-credential-value="ssid"]')?.textContent).toBe("Open LAN");
    expect(document.querySelector('[data-credential-value="password"]')).toBeNull();
  });
});
