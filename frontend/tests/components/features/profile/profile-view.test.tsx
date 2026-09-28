import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { User } from "@/entities/user";
import { ProfileView } from "@/features/profile";
import { fireEvent, render, screen, waitFor } from "@/tests/render-with-intl";

const httpMock = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
}));

const sessionMock = vi.hoisted(() => ({ setUser: vi.fn() }));

vi.mock("@/shared/http/client", () => ({
  authHttp: httpMock,
  localHttp: httpMock,
}));

vi.mock("@/features/auth", () => ({
  useSessionStore: { getState: () => sessionMock },
}));

const profile: User = {
  uuid: "user-1",
  username: "ada",
  firstName: "Ada",
  lastName: "Lovelace",
  emailAddress: { email: "ada@example.com", isVerified: true },
};

function renderView() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ProfileView />
    </QueryClientProvider>
  );
}

describe("ProfileView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the profile from the server cache into the form", async () => {
    httpMock.get.mockResolvedValue({ data: { data: profile } });

    renderView();

    expect(await screen.findByDisplayValue("Ada")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ada@example.com")).toBeInTheDocument();
    expect(httpMock.get).toHaveBeenCalledWith("/v1/me/profile");
  });

  it("shows a translated load error with a retry that recovers", async () => {
    httpMock.get
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce({ data: { data: profile } });

    renderView();

    expect(
      await screen.findByText("We couldn't load your profile.")
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByDisplayValue("Ada")).toBeInTheDocument();
  });

  it("saves the profile, updates the session user and confirms", async () => {
    const saved = { ...profile, firstName: "Augusta" };
    httpMock.get.mockResolvedValue({ data: { data: profile } });
    httpMock.put.mockResolvedValue({ data: { data: saved } });

    renderView();
    const firstName = await screen.findByLabelText("First name");
    fireEvent.change(firstName, { target: { value: "Augusta" } });
    fireEvent.click(screen.getByRole("button", { name: "Update profile" }));

    expect(
      await screen.findByText("Profile updated successfully")
    ).toBeInTheDocument();
    expect(httpMock.put).toHaveBeenCalledWith("/v1/me/profile", {
      firstName: "Augusta",
      lastName: "Lovelace",
    });
    expect(sessionMock.setUser).toHaveBeenCalledWith(saved);
  });

  it("falls back to a translated message when the password change fails without a backend message", async () => {
    httpMock.get.mockResolvedValue({ data: { data: profile } });
    httpMock.put.mockRejectedValue(new Error("network down"));

    renderView();
    await screen.findByDisplayValue("Ada");
    fireEvent.change(screen.getByLabelText("Current password"), {
      target: { value: "old-password" },
    });
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "new-password-123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm new password"), {
      target: { value: "new-password-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    await waitFor(() =>
      expect(
        screen.getByText("We couldn't change your password.")
      ).toBeInTheDocument()
    );
  });
});
