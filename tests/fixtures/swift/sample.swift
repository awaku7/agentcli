import Foundation

/// Person class.
class Person {
    var name: String
    var age: Int

    init(name: String, age: Int) {
        self.name = name
        self.age = age
    }

    func greet() -> String {
        return "Hello, \(name)"
    }

    func processAsync(id: Int, data: String) async -> Result {
        return await doWork(id: id, data: data)
    }
}

/// Repository protocol.
protocol Repository {
    associatedtype T
    func getById(id: Int) async throws -> T
    func save(entity: T) async throws
}

/// Status enum.
enum Status {
    case active
    case inactive
    case pending
}

/// Person struct.
struct PersonDto {
    let name: String
    let age: Int
}

/// PersonFactory extension on Person.
extension Person {
    static func create(name: String, age: Int) -> Person {
        return Person(name: name, age: age)
    }
}
