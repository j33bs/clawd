// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "coreml-embed-runner",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "CoreMLEmbedRunner", targets: ["CoreMLEmbedRunner"]),
    ],
    targets: [
        .executableTarget(
            name: "CoreMLEmbedRunner",
            path: "Sources/CoreMLEmbedRunner"
        ),
    ]
)
