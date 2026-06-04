import client from "./client";

export async function login(
  username,
  password,
) {
  const formData =
    new URLSearchParams();

  formData.append(
    "username",
    username,
  );

  formData.append(
    "password",
    password,
  );

  const response =
    await client.post(
      "/auth/login",
      formData,
      {
        headers: {
          "Content-Type":
            "application/x-www-form-urlencoded",
        },
      },
    );

  return response.data;
}