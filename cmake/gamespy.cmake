set(GS_OPENSSL FALSE)
set(GAMESPY_SERVER_NAME "server.cnc-online.net")

FetchContent_Declare(
    gamespy
    GIT_REPOSITORY https://github.com/TheAssemblyArmada/GamespySDK.git
    GIT_TAG        07e3d15c500415abc281efb74322ab6d9c857eb8
    # GeneralsX @bugfix Codex 31/10/2026 Compare protocol values in their own enum domains without warning suppression.
    PATCH_COMMAND ${CMAKE_COMMAND}
        -DSOURCE_DIR=<SOURCE_DIR>
        -DPATCH_FILE=${CMAKE_SOURCE_DIR}/Patches/gamespy-enum-domains.patch
        -P ${CMAKE_SOURCE_DIR}/cmake/apply-vendored-patch.cmake
)

FetchContent_MakeAvailable(gamespy)
