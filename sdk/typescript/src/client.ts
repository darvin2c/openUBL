import createClient from "openapi-fetch";
import type { paths } from "./openubl-types.js";

export const client = createClient<paths>({ baseUrl: "http://localhost:8000" });
