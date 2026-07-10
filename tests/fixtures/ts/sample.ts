/// Core module
export namespace MyApp.Core {
    /// Person class
    export class Person {
        constructor(
            public name: string,
            public age: number
        ) {}

        greet(): string {
            return `Hello, ${this.name}`;
        }

        async processAsync(id: number, data: string): Promise<Result> {
            return await doWork(id, data);
        }

        toString(): string {
            return `${this.name} (${this.age})`;
        }
    }

    /// Generic repository interface
    export interface Repository<T> {
        getById(id: number): Promise<T>;
        save(entity: T): Promise<void>;
    }

    export enum Status {
        Active,
        Inactive,
        Pending,
    }

    export type PersonDto = {
        name: string;
        age: number;
    };

    export function createPerson(name: string, age: number): Person {
        return new Person(name, age);
    }
}
