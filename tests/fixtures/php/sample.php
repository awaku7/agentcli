<?php

namespace MyApp\Core;

/**
 * Person class.
 */
#[Serializable]
class Person {
    public function __construct(
        public string $name,
        public int $age
    ) {}

    public function greet(): string {
        return "Hello, $this->name";
    }

    public static function create(string $name, int $age): self {
        return new self($name, $age);
    }
}

/**
 * Repository interface.
 */
interface Repository {
    public function findById(int $id): ?object;
    public function save(object $entity): void;
}

trait Loggable {
    public function log(string $message): void {
        echo "[LOG] $message";
    }
}

enum Status: string {
    case Active = 'active';
    case Inactive = 'inactive';
}
