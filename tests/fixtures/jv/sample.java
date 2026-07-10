package com.myapp.core;

import java.util.concurrent.CompletableFuture;

/**
 * Represents a person entity.
 */
public class Person {
    private String name;
    private int age;

    public Person(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() { return name; }
    public int getAge() { return age; }

    public CompletableFuture<Result> processAsync(int id, String data) {
        return doWork(id, data);
    }

    @Override
    public String toString() {
        return name + " (" + age + ")";
    }
}

/**
 * Generic repository interface.
 */
interface Repository<T> {
    CompletableFuture<T> getById(int id);
    CompletableFuture<Void> save(T entity);
}

enum Status {
    ACTIVE,
    INACTIVE,
    PENDING
}

record PersonDto(String name, int age) {}

final class PersonFactory {
    private PersonFactory() {}
    static Person create(String name, int age) { return new Person(name, age); }
}
