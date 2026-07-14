/** @type {import('jest').Config} */
const config = {
    preset: "ts-jest",
    testEnvironment: "jest-environment-jsdom",
    passWithNoTests: true,
    moduleNameMapper: {
        "^@/(.*)$": "<rootDir>/src/$1",
    },
};

module.exports = config;
