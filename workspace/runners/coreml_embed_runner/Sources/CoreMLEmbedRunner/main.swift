import Foundation
import CoreML

enum RunnerErrorType: String {
    case modelNotFound = "MODEL_NOT_FOUND"
    case modelLoadFailed = "MODEL_LOAD_FAILED"
    case invalidInput = "INVALID_INPUT"
    case inferenceFailed = "INFERENCE_FAILED"
    case unsupportedModelIO = "UNSUPPORTED_MODEL_IO"
}

struct RunnerInput: Decodable {
    let model_path: String
    let texts: [String]
    let max_text_chars: Int?
    let compute_units: String?
}

struct RunnerErrorPayload: Encodable {
    let type: String
    let message: String
    let details: [String: String]
}

struct RunnerFailure: Encodable {
    let ok: Bool = false
    let error: RunnerErrorPayload
}

struct RunnerSuccess: Encodable {
    let ok: Bool = true
    let model_path: String
    let dims: Int
    let embeddings: [[Double]]
    let latency_ms: Int
}

struct HealthSuccess: Encodable {
    let ok: Bool = true
    let model_path: String
    let inputs: [String]
    let outputs: [String]
}

struct CliOptions {
    var health: Bool = false
    var modelPath: String?
    var computeUnits: String?
}

func writeJSON<T: Encodable>(_ value: T) {
    let encoder = JSONEncoder()
    if let data = try? encoder.encode(value), let text = String(data: data, encoding: .utf8) {
        FileHandle.standardOutput.write(Data((text + "\n").utf8))
    } else {
        FileHandle.standardOutput.write(Data("{\"ok\":false,\"error\":{\"type\":\"INFERENCE_FAILED\",\"message\":\"json encoding failed\",\"details\":{}}}\n".utf8))
    }
}

func fail(_ type: RunnerErrorType, _ message: String, details: [String: String] = [:]) -> Never {
    writeJSON(RunnerFailure(error: RunnerErrorPayload(type: type.rawValue, message: message, details: details)))
    exit(1)
}

func parseArgs() -> CliOptions {
    var options = CliOptions()
    let args = Array(CommandLine.arguments.dropFirst())
    var i = 0
    while i < args.count {
        let arg = args[i]
        if arg == "--health" {
            options.health = true
            i += 1
            continue
        }
        guard i + 1 < args.count else {
            fail(.invalidInput, "missing value for \(arg)")
        }
        let value = args[i + 1]
        if arg == "--model_path" {
            options.modelPath = value
        } else if arg == "--compute_units" {
            options.computeUnits = value
        } else {
            fail(.invalidInput, "unknown flag \(arg)")
        }
        i += 2
    }
    return options
}

func computeUnits(from raw: String?) -> MLComputeUnits {
    let key = (raw ?? "ALL").uppercased()
    switch key {
    case "CPU_ONLY":
        return .cpuOnly
    case "CPU_AND_GPU":
        return .cpuAndGPU
    case "CPU_AND_NE":
        if #available(macOS 13.0, *) {
            return .cpuAndNeuralEngine
        }
        return .all
    default:
        return .all
    }
}

func loadModel(at modelPath: String, computeUnits rawUnits: String?) -> MLModel {
    let url = URL(fileURLWithPath: modelPath)
    guard FileManager.default.fileExists(atPath: url.path) else {
        fail(.modelNotFound, "model_path does not exist", details: ["model_path": modelPath])
    }
    let cfg = MLModelConfiguration()
    cfg.computeUnits = computeUnits(from: rawUnits)
    do {
        return try MLModel(contentsOf: url, configuration: cfg)
    } catch {
        fail(.modelLoadFailed, "failed to load model", details: ["model_path": modelPath, "error": String(describing: error)])
    }
}

func modelTypeName(_ constraint: MLFeatureDescription) -> String {
    switch constraint.type {
    case .string:
        return "string"
    case .multiArray:
        return "multiArray"
    case .int64:
        return "int64"
    case .double:
        return "double"
    case .image:
        return "image"
    default:
        return "other"
    }
}

func resolveIO(_ model: MLModel) -> (String, String) {
    let inputs = model.modelDescription.inputDescriptionsByName
    let outputs = model.modelDescription.outputDescriptionsByName

    let inputName = inputs.first(where: { $0.value.type == .string })?.key
    let outputName = outputs.first(where: { $0.value.type == .multiArray })?.key

    guard let inName = inputName, let outName = outputName else {
        let inDesc = inputs.map { "\($0.key):\(modelTypeName($0.value))" }.joined(separator: ",")
        let outDesc = outputs.map { "\($0.key):\(modelTypeName($0.value))" }.joined(separator: ",")
        fail(
            .unsupportedModelIO,
            "unable to infer supported string->multiArray embedding IO",
            details: ["inputs": inDesc, "outputs": outDesc]
        )
    }
    return (inName, outName)
}

func multiArrayToDoubles(_ arr: MLMultiArray) -> [Double] {
    let count = arr.count
    var out = [Double](repeating: 0.0, count: count)

    switch arr.dataType {
    case .double:
        let ptr = arr.dataPointer.bindMemory(to: Double.self, capacity: count)
        for i in 0..<count { out[i] = ptr[i] }
    case .float32:
        let ptr = arr.dataPointer.bindMemory(to: Float.self, capacity: count)
        for i in 0..<count { out[i] = Double(ptr[i]) }
    case .float16:
        let ptr = arr.dataPointer.bindMemory(to: UInt16.self, capacity: count)
        for i in 0..<count { out[i] = Double(ptr[i]) }
    case .int32:
        let ptr = arr.dataPointer.bindMemory(to: Int32.self, capacity: count)
        for i in 0..<count { out[i] = Double(ptr[i]) }
    default:
        let ptr = arr.dataPointer.bindMemory(to: Double.self, capacity: count)
        for i in 0..<count { out[i] = ptr[i] }
    }
    return out
}

func readInputFromStdin() -> RunnerInput {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard !data.isEmpty else {
        fail(.invalidInput, "stdin JSON is required")
    }
    do {
        return try JSONDecoder().decode(RunnerInput.self, from: data)
    } catch {
        fail(.invalidInput, "failed to parse input JSON", details: ["error": String(describing: error)])
    }
}

func runHealth(modelPath: String, computeUnits: String?) {
    let model = loadModel(at: modelPath, computeUnits: computeUnits)
    _ = resolveIO(model)
    let inputs = model.modelDescription.inputDescriptionsByName.keys.sorted()
    let outputs = model.modelDescription.outputDescriptionsByName.keys.sorted()
    writeJSON(HealthSuccess(model_path: modelPath, inputs: inputs, outputs: outputs))
}

func runInference(input: RunnerInput) {
    if input.texts.isEmpty {
        fail(.invalidInput, "texts cannot be empty")
    }
    let maxChars = input.max_text_chars ?? 4000
    if maxChars < 1 {
        fail(.invalidInput, "max_text_chars must be >= 1")
    }
    for text in input.texts {
        if text.count > maxChars {
            fail(.invalidInput, "text exceeds max_text_chars", details: ["max_text_chars": String(maxChars)])
        }
    }

    let model = loadModel(at: input.model_path, computeUnits: input.compute_units)
    let (inputName, outputName) = resolveIO(model)

    let start = Date()
    var vectors: [[Double]] = []
    vectors.reserveCapacity(input.texts.count)

    for text in input.texts {
        do {
            let provider = try MLDictionaryFeatureProvider(dictionary: [inputName: MLFeatureValue(string: text)])
            let result = try model.prediction(from: provider)
            guard let feature = result.featureValue(for: outputName), let arr = feature.multiArrayValue else {
                fail(.inferenceFailed, "missing embedding output", details: ["output_name": outputName])
            }
            vectors.append(multiArrayToDoubles(arr))
        } catch {
            fail(.inferenceFailed, "model inference failed", details: ["error": String(describing: error)])
        }
    }

    let latencyMs = Int(Date().timeIntervalSince(start) * 1000.0)
    let dims = vectors.first?.count ?? 0
    writeJSON(RunnerSuccess(model_path: input.model_path, dims: dims, embeddings: vectors, latency_ms: latencyMs))
}

let options = parseArgs()
if options.health {
    guard let modelPath = options.modelPath, !modelPath.isEmpty else {
        fail(.invalidInput, "--model_path is required for --health")
    }
    runHealth(modelPath: modelPath, computeUnits: options.computeUnits)
} else {
    let input = readInputFromStdin()
    runInference(input: input)
}
