import { setupServer } from "msw/node";

import { getBanxumApiMock } from "../generated/banxumApi";

export const server = setupServer(...getBanxumApiMock());
