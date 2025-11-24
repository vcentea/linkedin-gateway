@echo off
IF "%1"=="prod" (
  echo Building LinkedIn Gateway Extension v2 for PRODUCTION...
  npx webpack --config webpack.config.prod.v2.js
  echo Production build completed. Check the dist-prod directory.
) ELSE (
  echo Building LinkedIn Gateway Extension v2 for DEVELOPMENT...
  npx webpack --config webpack.config.v2.js
  echo Development build completed. Check the dist-dev directory.
) 