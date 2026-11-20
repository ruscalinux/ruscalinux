# ---------------------------------------------------------------------------
# RuscaLinux — ruscapiper-engine: compila libpiper e ruscapiper-stream.
# GPL-3.0-or-later. La lancia make-deb.sh: non serve usarla a mano.
#
# Perché una build propria e non libpiper/CMakeLists.txt di Piper: quella,
# durante la configurazione, scarica espeak-ng con git (ExternalProject) e,
# se non trova ONNX Runtime nel sistema, anche quello da GitHub. Le regole di
# RuscaLinux vogliono la compilazione senza rete e sorgenti verificati. Qui
# si compilano gli STESSI file sorgente di Piper, senza modificarli:
#   * espeak-ng arriva già compilato da make-deb.sh (la revisione fissata da
#     Piper, verificata con il commit e con l'impronta SHA-256), statico;
#   * ONNX Runtime è quello di Debian (libonnxruntime-dev).
#
# Variabili (da make-deb.sh):
#   PIPER_SRC          sorgente di piper1-gpl (la cartella con libpiper/)
#   ESPEAK_INSTALL     espeak-ng installato (include/, lib/libespeak-ng.a)
#   UCD_LIB            libucd.a della build di espeak-ng
#   PIPER_VERSION      versione di Piper (da setup.py)
#   RUSCAPIPER_VERSION versione di RuscaLinux
#   RUSCAPIPER_ESPEAK_DATA  dove il pacchetto installa espeak-ng-data
#   ORT_ROOT           facoltativa: ONNX Runtime fuori dal sistema
#                      (include/ e lib/), solo per prove
# ---------------------------------------------------------------------------
cmake_minimum_required(VERSION 3.25)
project(ruscapiper LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)

foreach(v PIPER_SRC ESPEAK_INSTALL UCD_LIB PIPER_VERSION RUSCAPIPER_VERSION RUSCAPIPER_ESPEAK_DATA)
  if(NOT DEFINED ${v})
    message(FATAL_ERROR "manca la variabile ${v}")
  endif()
endforeach()

# ---- ONNX Runtime: quello di Debian ----
if(DEFINED ORT_ROOT)
  find_path(ORT_INCLUDE onnxruntime_cxx_api.h
            PATHS ${ORT_ROOT}/include ${ORT_ROOT}/include/onnxruntime NO_DEFAULT_PATH REQUIRED)
  find_library(ORT_LIB onnxruntime PATHS ${ORT_ROOT}/lib NO_DEFAULT_PATH REQUIRED)
  add_library(ort UNKNOWN IMPORTED)
  set_target_properties(ort PROPERTIES IMPORTED_LOCATION ${ORT_LIB}
                        INTERFACE_INCLUDE_DIRECTORIES ${ORT_INCLUDE})
  set(ORT_TARGET ort)
else()
  find_package(onnxruntime CONFIG QUIET)
  if(TARGET onnxruntime::onnxruntime)
    set(ORT_TARGET onnxruntime::onnxruntime)
    message(STATUS "ONNX Runtime: configurazione CMake del sistema (${onnxruntime_VERSION})")
  else()
    find_path(ORT_INCLUDE onnxruntime_cxx_api.h
              PATH_SUFFIXES onnxruntime onnxruntime/core/session)
    find_library(ORT_LIB onnxruntime)
    if(NOT ORT_INCLUDE OR NOT ORT_LIB)
      message(FATAL_ERROR "ONNX Runtime non trovato: sudo apt install libonnxruntime-dev")
    endif()
    add_library(ort UNKNOWN IMPORTED)
    set_target_properties(ort PROPERTIES IMPORTED_LOCATION ${ORT_LIB}
                          INTERFACE_INCLUDE_DIRECTORIES ${ORT_INCLUDE})
    set(ORT_TARGET ort)
    message(STATUS "ONNX Runtime: ${ORT_LIB} (${ORT_INCLUDE})")
  endif()
endif()
# Alcune installazioni mettono le intestazioni in include/ e altre in
# include/onnxruntime/: piper.cpp le include senza cartella.
get_target_property(_ort_inc ${ORT_TARGET} INTERFACE_INCLUDE_DIRECTORIES)
set(ORT_EXTRA_INC "")
foreach(d ${_ort_inc})
  if(EXISTS "${d}/onnxruntime/onnxruntime_cxx_api.h")
    list(APPEND ORT_EXTRA_INC "${d}/onnxruntime")
  endif()
endforeach()

# ---- libpiper: i file di Piper, invariati ----
add_library(piper SHARED
  ${PIPER_SRC}/libpiper/src/piper.cpp
  ${PIPER_SRC}/libpiper/src/chinese_phonemizer.cpp)
target_include_directories(piper
  PUBLIC ${PIPER_SRC}/libpiper/include
  PRIVATE ${ESPEAK_INSTALL}/include ${ORT_EXTRA_INC})
target_compile_definitions(piper PRIVATE
  PIPER_VERSION="${PIPER_VERSION}" BUILDING_LIBPIPER)
target_link_libraries(piper PRIVATE
  ${ESPEAK_INSTALL}/lib/libespeak-ng.a ${UCD_LIB} ${ORT_TARGET})
set_target_properties(piper PROPERTIES POSITION_INDEPENDENT_CODE ON)

# ---- ruscapiper-stream: codice di RuscaLinux ----
add_executable(ruscapiper-stream ${CMAKE_CURRENT_SOURCE_DIR}/ruscapiper-stream.c)
target_compile_definitions(ruscapiper-stream PRIVATE
  RUSCAPIPER_VERSION="${RUSCAPIPER_VERSION}"
  RUSCAPIPER_ESPEAK_DATA="${RUSCAPIPER_ESPEAK_DATA}")
target_compile_options(ruscapiper-stream PRIVATE -Wall -Wextra)
target_link_libraries(ruscapiper-stream PRIVATE piper m)
