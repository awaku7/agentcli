import 'dart:async';

/// Core library
library myapp.core;

/// Person class
class Person {
  String name;
  int age;

  Person(this.name, this.age);

  String get greeting => 'Hello, $name';

  Future<Result> processAsync(int id, String data) async {
    return await doWork(id, data);
  }

  @override
  String toString() => '$name ($age)';
}

/// Generic repository interface
abstract class Repository<T> {
  Future<T> getById(int id);
  Future<void> save(T entity);
}

/// Status enum
enum Status { active, inactive, pending }

/// Person record
class PersonDto {
  final String name;
  final int age;

  const PersonDto(this.name, this.age);
}

/// Factory mixin
mixin PersonFactory {
  Person create(String name, int age) => Person(name, age);
}

/// Extension on String
extension StringGreeting on String {
  String get greet => 'Hi, $this!';
}
