// eslint-disable-next-line no-unused-vars
export function errorHandler(err, req, res, next) {
  console.error("[API Error]", err.message);

  const isProd = process.env.NODE_ENV === "production";

  res.status(err.status || 500).json({
    error: err.message || "Internal server error",
    ...(isProd ? {} : { stack: err.stack }),
  });
}
