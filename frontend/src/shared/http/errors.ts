import axios, { type AxiosError } from "axios";

export interface ErrorItem {
  message: string;
  code: string;
}

export interface ValidationFeedback {
  code: string;
  message: string;
}

export interface ErrorFeedback {
  errors: ErrorItem[];
  validation: Record<string, ValidationFeedback> | null;
}

// Backward-compatible alias for the existing misspelled exported type.
export type ErrorFeeback = ErrorFeedback;

export const emptyErrorFeedback: ErrorFeedback = {
  errors: [],
  validation: null,
};

export const genericServerError: ErrorFeedback = {
  errors: [
    {
      code: "client.ServerError",
      message: "Something went wrong.",
    },
  ],
  validation: null,
};

export const invalidCredentials: ErrorFeedback = {
  errors: [
    {
      code: "auth.InvalidCredentials",
      message: "Invalid Credentials!",
    },
  ],
  validation: null,
};

export const invalidRefreshToken: ErrorFeedback = {
  errors: [
    {
      code: "client.InvalidRefreshToken",
      message: "Invalid Refresh Token!",
    },
  ],
  validation: null,
};

export const refreshCookieNotFound: ErrorFeedback = {
  errors: [
    {
      code: "client.RefreshCookieNotFound",
      message: "Invalid Refresh Token Cookie!",
    },
  ],
  validation: null,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isErrorItem(value: unknown): value is ErrorItem {
  if (!isRecord(value)) return false;
  return typeof value.code === "string" && typeof value.message === "string";
}

function parseValidation(
  value: unknown
): Record<string, ValidationFeedback> | null {
  if (!isRecord(value)) return null;

  const validation: Record<string, ValidationFeedback> = {};
  for (const [key, item] of Object.entries(value)) {
    if (!isRecord(item)) continue;
    if (typeof item.code !== "string" || typeof item.message !== "string") {
      continue;
    }
    validation[key] = { code: item.code, message: item.message };
  }
  return Object.keys(validation).length > 0 ? validation : null;
}

export function isErrorFeedback(value: unknown): value is ErrorFeedback {
  if (!isRecord(value)) return false;
  return Array.isArray(value.errors) && value.errors.every(isErrorItem);
}

export function normalizeErrorFeedback(value: unknown): ErrorFeedback | null {
  if (!isErrorFeedback(value)) return null;
  return {
    errors: value.errors,
    validation: parseValidation(value.validation),
  };
}

export function handleHttpError(error: unknown): ErrorFeedback {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    const structured = normalizeErrorFeedback(data);
    if (structured) return structured;

    if (isRecord(data) && typeof data.message === "string") {
      return {
        errors: [
          {
            code: `HTTP_${error.response?.status ?? 0}`,
            message: data.message,
          },
        ],
        validation: parseValidation(data.validation),
      };
    }

    return errorFromStatus(error);
  }

  return genericServerError;
}

export function errorFromAxios(
  error: unknown,
  fallbackMessage: string
): ErrorFeedback {
  if (!axios.isAxiosError(error)) return genericServerError;

  const structured = normalizeErrorFeedback(error.response?.data);
  if (structured) return structured;

  if (isRecord(error.response?.data)) {
    const data = error.response.data;
    const message =
      typeof data.message === "string" ? data.message : fallbackMessage;
    const rawCode = data.code;
    const code =
      error.response?.status?.toString() ||
      (typeof rawCode === "string" ? rawCode : "UNKNOWN_ERROR");

    return {
      errors: [{ message, code }],
      validation: parseValidation(data.validation),
    };
  }

  return {
    errors: [
      {
        message: fallbackMessage,
        code: error.response?.status?.toString() || "UNKNOWN_ERROR",
      },
    ],
    validation: null,
  };
}

function errorFromStatus(error: AxiosError): ErrorFeedback {
  const statusCode = error.response?.status || 0;
  let message = "Error desconocido";
  let code = "UNKNOWN_ERROR";

  switch (statusCode) {
    case 400:
      message = "Solicitud invalida";
      code = "BAD_REQUEST";
      break;
    case 401:
      message = "No autorizado";
      code = "UNAUTHORIZED";
      break;
    case 403:
      message = "Acceso denegado";
      code = "FORBIDDEN";
      break;
    case 404:
      message = "Recurso no encontrado";
      code = "NOT_FOUND";
      break;
    case 409:
      message = "Conflicto de datos";
      code = "CONFLICT";
      break;
    case 422:
      message = "Datos de validacion incorrectos";
      code = "VALIDATION_ERROR";
      break;
    case 429:
      message = "Demasiadas solicitudes";
      code = "RATE_LIMIT";
      break;
    case 500:
      message = "Error interno del servidor";
      code = "INTERNAL_SERVER_ERROR";
      break;
    case 502:
      message = "Gateway incorrecto";
      code = "BAD_GATEWAY";
      break;
    case 503:
      message = "Servicio no disponible";
      code = "SERVICE_UNAVAILABLE";
      break;
    case 504:
      message = "Timeout del gateway";
      code = "GATEWAY_TIMEOUT";
      break;
    default:
      if (statusCode >= 500) {
        message = "Error del servidor";
        code = "SERVER_ERROR";
      } else if (statusCode >= 400) {
        message = "Error en la solicitud";
        code = "CLIENT_ERROR";
      } else {
        message = error.message || "Error de conexion";
        code = "NETWORK_ERROR";
      }
  }

  return {
    errors: [{ code, message }],
    validation: null,
  };
}

export function getFirstErrorMessage(errorFeedback: ErrorFeedback): string {
  return errorFeedback.errors[0]?.message ?? "Error desconocido";
}

export function isAuthError(error: AxiosError): boolean {
  return error.response?.status === 401;
}

export function isValidationError(error: AxiosError): boolean {
  return error.response?.status === 422;
}

export function isBadRequestError(error: AxiosError): boolean {
  return error.response?.status === 400;
}

export function showErrorItems(errors: ErrorItem[]): string {
  return errors.map((error) => error.message).join(", ");
}
